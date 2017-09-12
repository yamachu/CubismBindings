# Copyright(c) Live2D Inc. All rights reserved.
# 
# Use of this source code is governed by the Live2D Open Software license
# that can be found at http://live2d.com/eula/live2d-open-software-license-agreement_en.html.


"""Provides base class for binding generators."""


import os
import pystache
import yaml


class GenBase(object):
    """Base class for binding generators."""


    def __init__(self, options):
        """Initializes instance."""
        # Store options.
        self.datadir = options.datadir
        self.templatesdir = options.templatesdir
        self.infiles = options.infiles
        self.outdir = options.outdir
        # Read YAMLs and patch them.
        self.yaml = self.loadyaml(options.yamlfiles[0])
        for y in range(len(options.yamlfiles)):
            if y == 0:
                continue
            # HACK Join top level keys as lists...
            b = self.loadyaml(options.yamlfiles[y])
            for key, values in b.items():
                if key in self.yaml:
                    self.yaml[key] += values
                else:
                    self.yaml[key] = values
        # Initialize containers
        self.data = self.yaml.copy()
        # Add warning and patch data further.
        self.data['autogeneratedwarning'] = 'THIS FILE WAS AUTO-GENERATED. ALL CHANGES WILL BE LOST UPON RE-GENERATION.'
        _patchdata(self.data)


    def loadyaml(self, path):
        """Conveniently allows reading YAMLs relative to data folder"""
        return yaml.load(_readcontents(os.path.join(self.datadir, path)))


    def run(self):
        """Triggers code generation"""
        for inpath in self.infiles:
            template = _readcontents(os.path.join(self.templatesdir, inpath))
            contents = pystache.render(template, self.data)
            outpath = os.path.join(self.outdir, inpath)
            _writecontents(contents, outpath)



def _readcontents(path):
    """Reads file contents."""
    stream = open(path, 'r')
    contents = stream.read()
    stream.close()
    return contents


def _writecontents(contents, path):
    """Writes contents to file."""
    if not os.path.exists(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))
    with open(path, 'w') as stream:
        stream.write(contents)


def _topropname(func):
    """Converts function entry to property name"""
    propname = func['entry'].replace('csmGet', '').replace(func['class'], '').replace(func['class'][:-1], '')
    return propname[0].lower() + propname[1:]


def _topropdoc(func):
    """Converts function doc to property doc"""
    propdoc = func['doc'].replace('Gets', '').strip()
    return propdoc[0].upper() + propdoc[1:]


def _tofuncname(func):
    """Converts function entry to function name."""
    funcname = func['entry'].replace('csm', '').replace(func['class'], '').replace(func['class'][:-1], '')
    return funcname[0].lower() + funcname[1:]


def _tofuncdoc(func):
    """Returns function doc."""
    return func['doc']


def _isproperty(func):
    """Checks whether function should be treated as property."""
    if not func['entry'].startswith('csmGet'):
        return False
    if not func['class'][:-1] in func['entry']:
        return False
    return True


def _isscalarproperty(func):
    """Checks whether function should be treated as scalar property."""
    if not _isproperty(func):
        return False
    if _isscalararray2property(func):
        return False
    if _isscalararrayproperty(func):
        return False
    if _isstringarrayproperty(func):
        return False
    return True


def _isscalararray2property(func):
    """Checks whether function should be treated as 2D scalar array property."""
    if not _isproperty(func):
        return False
    return func['return']['type'].endswith('Array2')


def _isscalararrayproperty(func):
    """Checks whether function should be treated as 1D scalar array property."""
    if not _isproperty(func):
        return False
    if not func['return']['type'].endswith('Array'):
        return False
    return func['return']['type'] != 'StringArray'


def _isstringarrayproperty(func):
    """Checks whether function should be treated as string array property."""
    if not _isproperty(func):
        return False
    return func['return']['type'] == 'StringArray'


def _patchdata(data):
    """Patches YAML data."""
    # Initializes additional containers.
    clsmap = {}
    # Patch enums.
    for enum in data['enums']:
        for entry in enum['entries']:
            valuename = entry['name'].replace('csm', '')
            entry['valuedoc'] = entry['doc']
            entry['valuename'] = valuename[0].lower() + valuename[1:]
            entry['Valuename'] = valuename
    # Patch flags.
    for flags in data['flags']:
        for i, entry in enumerate(flags['entries']):
            flagname = entry['name'].replace('csm', '')
            entry['flagdoc'] = entry['doc']
            entry['flagname'] = flagname[0].lower() + flagname[1:]
            entry['Flagname'] = flagname
            entry['flagindex'] = i
    # Patch functions.
    for func in data['functions']:
        # Get class matching function.
        cls = _getoradd((func['class'][0].lower() + func['class'][1:]), clsmap, {
            'doc': func['class'][0].upper() + func['class'][1:],
            'name': func['class'][0].lower() + func['class'][1:],
            'Name': func['class'],
            'type': func['class'],
            'props': [],
            'funcs': []
        })
        # Patch names and docs to args and returns.
        if 'args' in func:
            for arg in func['args']:
                _getoradd('doc', arg, arg['type'])
                _getoradd('name', arg, arg['type'].lower())
        if 'return' in func:
            # INV Patch in doc?
            pass      
        # Append function to class.
        if _isproperty(func):
            func['propdoc'] = _topropdoc(func)
            func['propname'] = _topropname(func)
            func['Propname'] = func['propname'][0].upper() + func['propname'][1:]
            cls['hasprops'] = True
            cls['props'].append(func)
        else:
            func['funcdoc'] = _tofuncdoc(func)
            func['funcname'] = _tofuncname(func)
            func['Funcname'] = func['funcname'][0].upper() + func['funcname'][1:]
            cls['hasfuncs'] = True
            cls['funcs'].append(func)
    # Provide shorthand for functions
    data['funcs'] = data['functions']
    # 'Sort' properties.
    for cls in clsmap.itervalues():
        scalarprops = []
        scalararrayprops = []
        scalararray2props = []
        stringarrayprops = []
        for prop in cls['props']:
            prop['propdoc'] = _topropdoc(prop)
            prop['proptype'] = prop['return']['type']
            prop['propget'] = prop['entry']
            if _isscalararray2property(prop):
                prop['propscalartype'] = prop['proptype'].split('Array')[0]
                prop['propgetlength'] = prop['return']['length'].split(' ')[0]
                if '*' in prop['return']['length']:
                    prop['proplengthfactor'] = prop['return']['length'].split('*')[1].strip()
                prop['propgetlength2'] = prop['return']['length2'].split(' ')[0]
                if '*' in prop['return']['length2']:
                    prop['proplength2factor'] = prop['return']['length2'].split('*')[1].strip()
                cls['hasarrayprop'] = True
                cls['hasarray2prop'] = True
                scalararray2props.append(prop)
            elif _isscalararrayproperty(prop):
                prop['propscalartype'] = prop['proptype'].split('Array')[0]
                prop['propgetlength'] = prop['return']['length'].split(' ')[0]
                if '*' in prop['return']['length']:
                    prop['propgetlengthfactor'] = prop['return']['length'].split(' ')[1].strip()
                cls['hasarrayprop'] = True
                scalararrayprops.append(prop)
            elif _isstringarrayproperty(prop):
                prop['propscalartype'] = prop['proptype']
                prop['propgetlength'] = prop['return']['length']
                cls['hasarrayprop'] = True
                stringarrayprops.append(prop)
            else:
                assert(_isscalarproperty(prop))
                prop['propscalartype'] = prop['proptype']
                scalarprops.append(prop)
        cls['scalarprops'] = scalarprops
        cls['scalararrayprops'] = scalararrayprops
        cls['scalararray2props'] = scalararray2props
        cls['stringarrayprops'] = stringarrayprops
        # Make sure all props have been sorted
        assert(len(cls['props']) == (len(scalarprops) + len(scalararrayprops) + len(scalararray2props) + len(stringarrayprops)))
    # Store additional containers.
    data['clsmap'] = clsmap
    return data


def _getoradd(key, indict, value):
    """Adds pair to dictionary unless key exists"""
    if not key in indict:
        indict[key] = value
    return indict[key]
