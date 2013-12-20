"""
Misc useful stuff.
"""
from __future__ import with_statement
import stat
import sys
import os
import shutil
import time
import posixpath
import ntpath
import UserDict
import subprocess as sp



WRITE_PERMS = stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH

def gen_dotgraph_image(dot_data, out_file):

    # shortcut if writing .dot file
    if out_file.endswith(".dot"):
        with open(out_file, 'w') as f:
            f.write(dot_data)
        return

    import pydot
    graph = pydot.graph_from_dot_data(dot_data)

    # assume write format from image extension
    ext = "jpg"
    if(out_file.rfind('.') != -1):
        ext = out_file.split('.')[-1]

    try:
        fn = getattr(graph, "write_" + ext)
    except Exception:
        sys.stderr.write("could not write to '" + out_file + "': unknown format specified")
        sys.exit(1)

    fn(out_file)

def which(*programs):
    for prog in programs:
        p = sp.Popen("which "+prog, shell=True, stdout=sp.PIPE, stderr=sp.PIPE)
        s_out,s_err = p.communicate()
        if not p.returncode:
            return s_out.strip()
    return None

def readable_time_duration(secs, approx=True):
    divs = ((24 * 60 * 60, "days"), (60 * 60, "hours"), (60, "minutes"), (1, "seconds"))

    if secs == 0:
        return "0 seconds"
    neg = (secs < 0)
    if neg:
        secs = -secs

    if approx:
        for i, s in enumerate([x[0] for x in divs[:-1]]):
            ss = float(s) * 0.9
            if secs >= ss:
                n = secs / s
                frac = float((secs + s) % s) / float(s)
                if frac < 0.1:
                    secs = n * s
                elif frac > 0.9:
                    secs = (n + 1) * s
                else:
                    s2 = divs[i + 1][0]
                    secs -= secs % s2
                break

    toks = []
    for d in divs:
        if secs >= d[0]:
            n = secs / d[0]
            count = n * d[0]
            label = d[1]
            if n == 1:
                label = label[:-1]
            toks.append((n, label))
            secs -= count

    s = str(", ").join([("%d %s" % (x[0], x[1])) for x in toks])
    if neg:
        s = '-' + s
    return s

def hide_local_packages():
    import rez.filesys
    rez.filesys._g_syspaths = rez.filesys._g_syspaths_nolocal

def unhide_local_packages():
    import rez.filesys
    rez.filesys._g_syspaths = rez.filesys.get_system_package_paths()

def remove_write_perms(path):
    st = os.stat(path)
    mode = st.st_mode & ~WRITE_PERMS
    os.chmod(path, mode)

def copytree(src, dst, symlinks=False, ignore=None, hardlinks=False):
    '''
    copytree that supports hard-linking
    '''
    names = os.listdir(src)
    if ignore is not None:
        ignored_names = ignore(src, names)
    else:
        ignored_names = set()

    if hardlinks:
        def copy(srcname, dstname):
            try:
                # try hard-linking first
                os.link(srcname, dstname)
            except OSError:
                shutil.copy2(srcname, dstname)
    else:
        copy = shutil.copy2

    os.makedirs(dst)
    errors = []
    for name in names:
        if name in ignored_names:
            continue
        srcname = os.path.join(src, name)
        dstname = os.path.join(dst, name)
        try:
            if symlinks and os.path.islink(srcname):
                linkto = os.readlink(srcname)
                os.symlink(linkto, dstname)
            elif os.path.isdir(srcname):
                copytree(srcname, dstname, symlinks, ignore)
            else:
                copy(srcname, dstname)
        # XXX What about devices, sockets etc.?
        except (IOError, os.error) as why:
            errors.append((srcname, dstname, str(why)))
        # catch the Error from the recursive copytree so that we can
        # continue with other files
        except shutil.Error as err:
            errors.extend(err.args[0])
    try:
        shutil.copystat(src, dst)
    except shutil.WindowsError:
        # can't copy file access times on Windows
        pass
    except OSError as why:
        errors.extend((src, dst, str(why)))
    if errors:
        raise shutil.Error(errors)

def get_epoch_time():
    """
    get time since the epoch as an int
    TODO switch everything to UTC
    """
    return int(time.mktime(time.localtime()))

def safe_chmod(path, mode):
    "set the permissions mode on path, but only if it differs from the current mode."
    if stat.S_IMODE(os.stat(path).st_mode) != mode:
        os.chmod(path, mode)

def to_nativepath(path):
    return os.path.join(path.split('/'))

def to_ntpath(path):
    return ntpath.sep.join(path.split(posixpath.sep))

def to_posixpath(path):
    return posixpath.sep.join(path.split(ntpath.sep))

class AttrDict(dict):
    """
    A dictionary with attribute-based lookup.
    """
    def __getattr__(self, attr):
        if attr.startswith('__') and attr.endswith('__'):
            d = self.__dict__
        else:
            d = self
        try:
            return d[attr]
        except KeyError:
            raise AttributeError("'%s' object has no attribute '%s'" % (self.__class__.__name__, attr))

    def copy(self):
        return AttrDict(dict.copy(self))

class AttrDictWrapper(UserDict.UserDict):
    """
    Wrap a custom dictionary with attribute-based lookup.
    """
    def __init__(self, data):
        self.__dict__['data'] = data

    def __getattr__(self, attr):
        if attr.startswith('__') and attr.endswith('__'):
            d = self.__dict__
        else:
            d = self.data
        try:
            return d[attr]
        except KeyError:
            raise AttributeError("'%s' object has no attribute '%s'" % (self.__class__.__name__, attr))

    def __setattr__(self, attr, value):
        # For things like '__class__', for instance
        if attr.startswith('__') and attr.endswith('__'):
            super(AttrDictWrapper, self).__setattr__(attr, value)
        self.data[attr] = value


_templates = {}

# Note this is the vert start of adding support for pluggable project template, ala rez-make-project.
def render_template(template, **variables):
    """
    Returns template from template/<template>, rendered with the given variables.
    """
    templ = _templates.get(template)
    if not templ:
        import rez
        path = os.path.join(rez.module_root_path, "template", os.path.join(*(template.split('/'))))
        if os.path.exists(path):
            with open(path) as f:
                templ = f.read()
                _templates[template] = templ
        else:
            # TODO support template plugins, probably using Jinja2
            raise Exception("Unknown template '%s'" % template)

    return templ % variables