#!/usr/bin/python3
import sys, os, re
import shutil
import csv
import subprocess
import math
import jinja2
import os
import datetime

from jinja2 import Template
from locale import atof, setlocale, LC_NUMERIC

setlocale(LC_NUMERIC, "C")
from collections import deque
import json


class Printer:
    def __init__(self, REF, mode):
        self.color = 1
        self.layout = 0
        self.margin = 10
        self.queue = deque()
        self.done = deque()
        self.REF = REF
        self.path = os.path.abspath(os.path.join(".", mode))
        self.outpath = os.path.abspath(os.path.join(".", "output", mode))
        if not os.path.exists(self.outpath):
            os.makedirs(self.outpath)
        self._specific()
        self.jinja_env.filters["elegantjoin"] = Printer.elegantjoin
        self.jinja_env.filters["hours"] = Printer.hours2string
        self.jinja_env.filters["hoursnum"] = Printer.hours2num
        self.jinja_env.filters["semestre2year"] = Printer.semestre2year
        self.jinja_env.filters["year2semestre"] = Printer.year2semestre

    def debug(self, a):
        print(str(a))

    def _specific(self):
        pass

    def addTemplate(self, name, subjectstring, dictionary={}):
        self.queue.append([name, subjectstring, dictionary])
        return True

    def runOne(self):
        if not self.queue:
            return False
        one = self.queue.popleft()
        onebase = one[0]
        onebasestripped = re.sub(self.suffix, "", onebase)
        onesubject = one[1]
        oneversion = self.REF.getShortVersion()
        onedict = one[2]
        filename = (
            self.REF.id
            + "_"
            + onebasestripped
            + "_"
            + str(onesubject)
            + "_"
            + oneversion
            + self.suffix
        )
        outpath = os.path.join(self.outpath, filename)
        onedict["data"] = self.REF
        onedict["subject"] = onesubject
        onedict["printer"] = self
        with open(outpath, "w") as f:
            template = self.jinja_env.get_template(onebase)
            output = template.render(**onedict)
            print(output, file=f)
        return outpath

    def run(self):
        self.prologue()
        while self.queue:
            done = self.runOne()
            self.done.append(done)
            print(done)
        self.epilogue()

    def prologue(self):
        outassets = os.path.join(self.outpath, "assets")
        if not os.path.exists(outassets):
            os.makedirs(outassets)
            inassets = os.path.abspath(os.path.join(".", "assets"))
            self.copyAssets(inassets, outassets)
            inassets = os.path.abspath(os.path.join(self.path, "assets"))
            self.copyAssets(inassets, outassets)

    def epilogue(self):
        pass

    def copyAssets(self, inpath, out):
        if not os.path.exists(inpath):
            return 0
        files = os.listdir(inpath)
        c = 0
        for file in files:
            ffile = os.path.join(inpath, file)
            if os.path.isfile(ffile):
                c += 1
                shutil.copy(ffile, out)
        return c

    @staticmethod
    def semestre2year(a):
        idx = (int(a) + 1) // 2
        if idx > 0 and idx < 4:
            return idx
        raise Exception("Key " + str(int(idx)) + " out of range")

    @staticmethod
    def year2semestre(a):
        idx = int(a)
        if idx > 0 and idx < 4:
            return [str(idx * 2 - 1), str(idx * 2)]
        raise Exception("Key " + str(int(idx)) + " out of range")

    @staticmethod
    def hours2string(a):
        if isinstance(a, str):
            a = float(a)
        hour = math.floor(a)
        minu = math.floor(a * 60 - hour * 60)
        if minu > 9:
            return "{0}h{1}".format(hour, minu)
        elif minu > 0:
            return "{0}h0{1}".format(hour, minu)
        return str(hour) + "h"

    @staticmethod
    def hours2num(a):
        if a == 0:
            return ""
        hour = math.floor(a)
        minu = math.floor(100 * (a * 60 - hour * 60))
        if minu > 9:
            return "{0},{1}".format(hour, minu)
        elif minu > 0:
            return "{0},0{1}".format(hour, minu)
        return str(hour)

    @staticmethod
    def elegantjoin(ll):
        l = list(ll)
        if len(l) == 0:
            return ""
        if len(l) == 1:
            return l[0]
        return ", ".join([str(x) for x in l[0:-1]]) + " et " + str(l[-1])


class LaTeXPrinter(Printer):
    def _specific(self):
        self.suffix = ".tex"
        self.jinja_env = jinja2.Environment(
            block_start_string="\BLOCK{",
            block_end_string="}",
            variable_start_string="\VAR{",
            variable_end_string="}",
            comment_start_string="\#{",
            comment_end_string="}",
            line_statement_prefix="%%",
            line_comment_prefix="% #",
            trim_blocks=True,
            autoescape=False,
            loader=jinja2.FileSystemLoader(self.path),
        )
        self.latexconv = {
            " ": r"\,",
            "&": r"\&",
            "%": r"\%",
            "$": r"\$",
            "#": r"\#",
            "_": r"\_",
            "{": r"\{",
            "}": r"\}",
            "~": r"\textasciitilde{}",
            "^": r"\^{}",
            "\\": r"\textbackslash{}",
            "<": r"\textless{}",
            ">": r"\textgreater{}",
        }
        self.latexre = re.compile(
            "|".join(
                re.escape(str(key))
                for key in sorted(self.latexconv.keys(), key=lambda item: -len(item))
            )
        )
        self.jinja_env.filters["le"] = lambda x: self.LaTeXEscape(x)

    def epilogue(self):
        for texfile in self.done:
            wd = os.getcwd()
            dirname = os.path.dirname(texfile)
            os.chdir(dirname)
            subprocess.check_call(["lualatex", texfile])
            logfile = texfile[0:-3] + "log"
            rerun = True
            loopprotection = 0
            while rerun:
                loopprotection += 1
                rerun = False
                with open(logfile) as log:
                    for x in log.readlines():
                        if x[0:47] == "LaTeX Warning: Label(s) may have changed. Rerun":
                            rerun = True
                if rerun:
                    subprocess.check_call(["lualatex", texfile])
                if loopprotection > 4:
                    rerun = False
            os.chdir(wd)

    def LaTeXEscape(self, a):
        """
        :param text: a plain text message
        :return: the message escaped to appear correctly in LaTeX
        """
        if isinstance(a, list):
            b = []
            for x in a:
                b.append(
                    self.latexre.sub(lambda match: self.latexconv[match.group()], x)
                )
            return b
        else:
            res = self.latexre.sub(lambda match: self.latexconv[match.group()], str(a))
            return res


class HTMLPrinter(Printer):
    def _specific(self):
        self.suffix = ".html"
        self.jinja_env = jinja2.Environment(
            trim_blocks=True, loader=jinja2.FileSystemLoader(self.path)
        )


class JSONPrinter(Printer):
    def _specific(self):
        self.suffix = ".json"
        self.jinja_env = jinja2.Environment(
            trim_blocks=True,
            autoescape=False,
            loader=jinja2.FileSystemLoader(self.path),
        )


class DataError(Exception):
    def __init__(self, message):
        self.message = message


class CatalogError(Exception):
    def __init__(self, message):
        self.message = message


class SmartObject:
    class_props = []
    class_arrayprops = []
    class_subs = []
    class_fkeys = []
    class_singlefkey = []

    def __init__(self, id, d, backref=None, namespace=None):
        self.namespace = namespace
        self.parent = backref
        self.backref = [backref]
        self.id = id
        namespace.addObject(id, self)
        for i in self.class_props:
            if i in d:
                setattr(self, i, d[i])
            else:
                setattr(self, i, "")
        for i in self.class_arrayprops:
            if i in d:
                setattr(self, i, d[i])
            else:
                setattr(self, i, [])
        for i in self.class_subs:
            if i in d:
                func = getattr(self, "_add_" + i)
                e = {}
                for j in d[i]:
                    e[j] = func(j, d[i][j], backref=self, namespace=namespace)
                setattr(self, i, e)
            else:
                setattr(self, i, {})
        for i in self.class_fkeys:
            if i in d:
                setattr(self, i + "_fkey", d[i])
            else:
                setattr(self, i + "_fkey", [])
        for i in self.class_singlefkey:
            if i in d:
                setattr(self, i + "_fkey", d[i])
            else:
                setattr(self, i + "_fkey", None)
        for i in self.class_fkeys + self.class_singlefkey:
            namespace.dereferenceForeignKeys(self, i)
        a = set(
            self.class_props
            + self.class_arrayprops
            + self.class_subs
            + self.class_fkeys
            + self.class_singlefkey
            + ["id"]
        )
        forgotten = []
        for i in d:
            if i not in a:
                forgotten.append(i)
        if len(forgotten):
            print("Keys {} ignored in {}".format(", ".join(forgotten), str(type(self))))

    def isPlural(self):
        return 1

    def getName(self):
        if hasattr(self, "name"):
            return self.name
        if hasattr(self, "shortname"):
            return self.shortname
        return self.id

    def getShortname(self):
        if hasattr(self, "shortname"):
            return self.shortname
        if hasattr(self, "name"):
            return self.name
        return self.id

    def toJson(self):
        d = {"id": self.id}
        for i in self.class_props + self.class_arrayprops:
            if hasattr(self, i):
                d[i] = getattr(self, i)
        for i in self.class_subs:
            if hasattr(self, i):
                e = {}
                f = getattr(self, i)
                for j in f:
                    e[f[j].id] = f[j].toJson()
                d[i] = e
        for i in self.class_fkeys:
            if hasattr(self, i):
                e = []
                f = getattr(self, i)
                for j in f:
                    e.append(f[j].id)
                d[i] = e
        for i in self.class_singlefkey:
            if hasattr(self, i):
                f = getattr(self, i)
                d[i] = f.id
        return d

    def __str__(self):
        s = "<Object " + str(type(self)) + " " + str(self.id) + ">\n"
        d = self.toJson()
        dd = []
        for k in sorted(d.keys()):
            if k != "id":
                if type(d[k]) == str:
                    dd.append('  {}: "{}"'.format(k, d[k]))
                elif type(d[k]) == type([]):
                    dd.append("  {}: [{} elts]".format(k, len(d[k])))
                else:
                    dd.append("  {}: dict({} elts)".format(k, len(d[k])))
        s += ",\n".join(dd)
        return s

    def addBackref(self, object):
        self.backref.append(object)


class Catalog:
    def __init__(self, *pargs, **args):
        self.catalog = {}
        self.fkeys = []
        super().__init__(*pargs, **args)

    def addObject(self, id, object):
        if id in self.catalog:
            raise CatalogError("{} already exists in catalog".format(id))
        self.catalog[id] = object

    def getObject(self, id):
        if id in self.catalog:
            return self.catalog[id]
        raise CatalogError("{} is not in catalog".format(id))

    def dereferenceForeignKeys(self, object, key):
        self.fkeys.append((object, key))

    def dereferenceAll(self):
        while len(self.fkeys) > 0:
            (object, key) = self.fkeys.pop()
            d = {}
            l = getattr(object, key + "_fkey")
            if isinstance(l, str):
                try:
                    y = self.getObject(l)
                except (CatalogError):
                    raise CatalogError(
                        "Wrong dereference for key {} in field {} of object {}".format(
                            l, key, object.id
                        )
                    )
                y.addBackref(object)
                d = y
            else:
                for x in l:
                    try:
                        y = self.getObject(x)
                    except (CatalogError):
                        raise CatalogError(
                            "Wrong dereference for key {} in field {} of object {}".format(
                                x, key, object.id
                            )
                        )
                    d[x] = y
                    y.addBackref(object)
            setattr(object, key, d)


class Referentiel(Catalog, SmartObject):
    class_props = ["version", "author", "authorshort", "name", "number", "url"]
    class_arrayprops = ["introtxt"]
    class_subs = [
        "comp",
        "multicomp",
        "parcours",
        "multiparcours",
        "ress",
        "sae",
        "portfolio",
        "source",
        "hours",
    ]

    def __init__(self, id, d, backref=None):
        super().__init__(id, d, backref=backref, namespace=self)
        if "version" not in d or d["version"] == "":
            today = datetime.date.today()
            self.version = today.strftime("V%Y%m%d")

    def _add_comp(self, id, d, backref=None, namespace=None):
        return Competence(id, d, backref=backref, namespace=namespace)

    def _add_multicomp(self, id, d, backref=None, namespace=None):
        return CompositeCompetence(id, d, backref=backref, namespace=namespace)

    def _add_parcours(self, id, d, backref=None, namespace=None):
        return Parcours(id, d, backref=backref, namespace=namespace)

    def _add_multiparcours(self, id, d, backref=None, namespace=None):
        return CompositeParcours(id, d, backref=backref, namespace=namespace)

    def _add_ress(self, id, d, backref=None, namespace=None):
        return Ressource(id, d, backref=backref, namespace=namespace)

    def _add_sae(self, id, d, backref=None, namespace=None):
        return SAE(id, d, backref=backref, namespace=namespace)

    def _add_portfolio(self, id, d, backref=None, namespace=None):
        return Portfolio(id, d, backref=backref, namespace=namespace)

    def _add_source(self, id, d, backref=None, namespace=None):
        return Source(id, d, backref=backref, namespace=namespace)

    def _add_hours(self, id, d, backref=None, namespace=None):
        return Hours(id, d, backref=backref, namespace=namespace)

    def getShortVersion(self):
        x = re.match(r"^([-_.A-Za-z0-9]*).*$", self.version)
        if x:
            return x.group(1)
        else:
            return self.version

    def getParcours(self, bin=None):
        all = (self.parcours | self.multiparcours).values()
        if bin == None:
            return ParcoursSet(all)
        a = set()
        for x in bin:
            found = False
            for y in all:
                if y.getBin() == x:
                    a.add(y)
                    found = True
            if not found:
                for xx in x:
                    found = False
                    for y in self.parcours.values():
                        if y.getBin() == xx:
                            a.add(y)
                            found = True
                    if not found:
                        raise CatalogError("Bad bin")
        return ParcoursSet(a)

    def getSemestre(self):
        return sorted({m.sem for m in self.getModule()})

    def getYear(self):
        return sorted({Printer.semestre2year(m.sem) for m in self.getModule()})

    def getModule(
        self,
        onlyType=None,
        semestre=None,
        year=None,
        parcours=None,
        interparcours=None,
        bin=None,
    ):
        if onlyType == None:
            modules = self.sae | self.ress | self.portfolio
        else:
            modules = {}
            if "SAE" in onlyType:
                modules = modules | self.sae
            if "RESS" in onlyType:
                modules = modules | self.ress
            if "PORTFOLIO" in onlyType:
                modules = modules | self.portfolio
        modules = set(modules.values())
        sems = set()
        if year != None or semestre != None:
            if year != None:
                sems = set(Printer.year2semestre(year))
            elif semestre != None:
                sems = {semestre}
        if len(sems):
            modules = {x for x in modules if len({x.sem} & sems)}
        if parcours != None or interparcours != None:
            parc = set()
            if parcours != None:
                parc = {parcours}
            else:
                parc = {x for x in self.getParcours() if interparcours.intersects(x)}
            filtered = set()
            for p in parc:
                filtered = filtered | {x for x in modules if p in x.getParcours()}
            modules = filtered
        if bin != None:
            modules = {x for x in modules if x.getParcoursBin() == bin}
        return ModuleList(sorted(modules, key=lambda x: x.moduleType() + x.id))

    def getHours(self, onlyType=None, source=None, destination=None):
        if not hasattr(source, "__iter__") and source != None:
            source = {source.id}
        elif source == None:
            source = set()
        else:
            source = {x.id for x in source}
        if not hasattr(destination, "__iter__") and destination != None:
            destination = {destination.id}
        elif destination == None:
            destination = set()
        else:
            destination = {x.id for x in destination}
        a = set()
        for i in self.hours.values():
            print(i.source)
            s = i.source.id
            d = i.destination.id
            if s in source or len(source) == 0:
                if d in destination or len(destination) == 0:
                    if onlyType == None or i.type in onlyType:
                        a.add(i)
        return HoursSet(a)


class Competence(SmartObject):
    class_props = ["name", "number", "shortname"]
    class_arrayprops = ["component", "context", "description"]
    class_subs = ["subcomp"]

    def _add_subcomp(self, id, d, backref=None, namespace=None):
        return NiveauCompetence(id, d, backref=backref, namespace=namespace)


class CompositeCompetence(SmartObject):
    class_props = ["name", "number", "shortname"]
    class_subs = ["subcomp"]
    class_fkeys = ["indirect"]

    def _add_subcomp(self, id, d, backref=None, namespace=None):
        return NiveauCompetence(id, d, backref=backref, namespace=namespace)

    def isPlural(self):
        return 2


class NiveauCompetence(SmartObject):
    class_props = ["name", "level"]
    class_subs = ["ac", "ue"]

    def _add_ac(self, id, d, backref=None, namespace=None):
        return ApprentissageCritique(id, d, backref=backref, namespace=namespace)

    def _add_ue(self, id, d, backref=None, namespace=None):
        return UE(id, d, backref=backref, namespace=namespace)

    def getUE(self, semestre=None):
        if semestre == None:
            return self.ue
        for u in self.ue.values():
            if u.sem == semestre:
                return u
        return None

    def getParcours(self):
        a = set()
        for i in self.backref:
            if isinstance(i, Parcours):
                a.add(i)
            if isinstance(i, CompositeParcours):
                a = a | i.getExpandedSet()
        return ParcoursSet(a)


class ApprentissageCritique(SmartObject):
    class_props = ["name", "num", "shortname"]


class UE(SmartObject):
    class_props = ["sem", "ects"]
    class_fkeys = ["parcours"]

    def getCoeff(self, module=None):
        if module == None:
            return CoefficientSet(
                {x for x in self.backref if isinstance(x, Coefficient)}
            )
        else:
            return CoefficientSet(
                {
                    x
                    for x in self.backref
                    if isinstance(x, Coefficient) and x.parent in module
                }
            )

    def getName(self):
        return (
            "UE "
            + self.sem
            + "."
            + self.parent.parent.number
            + " ("
            + self.getParcours().getCanonical()
            + ")"
        )

    def getShortname(self):
        return (
            "UE "
            + self.sem
            + "."
            + self.parent.parent.number
            + " ("
            + self.getParcours().getCanonical(short=True)
            + ")"
        )

    def getParts(self):
        return (
            "UE " + self.sem + "." + self.parent.parent.number,
            ParcoursSet(self.getParcours()),
        )

    def getParcours(self):
        return ParcoursSet(self.parcours.values())


class Parcours(SmartObject):
    class_props = ["letter", "name", "shortname"]
    class_arrayprops = ["introtxt", "job", "jobsecondary", "jobsenior"]
    class_fkeys = ["subcomp"]

    def intersects(self, p):
        if self in p.getExpandedSet():
            return True
        return False

    def getExpandedSet(self):
        return ParcoursSet({self})

    def getCanonical(self, lower=True, short=False):
        if short:
            return self.letter
        return ("p" if lower else "P") + "arcours " + self.letter

    def getCompLevel(self, year=None):
        if year == None:
            sc = set(self.subcomp.values())
        else:
            y = str(year)
            sc = {x for x in self.subcomp.values() if x.level == y}
        return sc

    def getBin(self):
        return self.letter


class CompositeParcours(SmartObject):
    class_props = ["letter", "name", "shortname"]
    class_fkeys = ["indirect"]

    def intersects(self, p):
        a = self.getExpandedSet()
        if len(a & p.getExpandedSet()) > 0:
            return True
        return False

    def getExpandedSet(self):
        s = set()
        for x in self.indirect.values():
            s = s | x.getExpandedSet()
        return ParcoursSet(s)

    def getCanonical(self, lower=True, short=False):
        t = self.letter
        if short:
            t = re.sub(" *parcours *", "", t)
        if lower:
            return t[0].lower() + t[1:]
        return t[0].upper() + t[1:]

    def isPlural(self):
        return 2

    def getCompLevel(self, year=None):
        a = None
        for t in self.indirect.values():
            b = t.getCompLevel(year=year)
            if a == None:
                a = b
            else:
                a = a & b
        return a

    def getBin(self):
        return "".join(sorted([x.letter for x in self.indirect.values()]))


class ParcoursSet(set):
    def getCanonical(self, lower=True, short=False):
        t = set()
        for p in self:
            t = t | p.getExpandedSet()
        if len(t) == 0:
            if short:
                return "aucun"
            else:
                return "hors parcours"
        for i in self:
            namespace = i.namespace
            break
        for p in namespace.getParcours():
            pp = p.getExpandedSet()
            if len(t & pp) == len(t) and len(t) == len(pp):
                return p.getCanonical(lower=lower, short=short)
        s = ""
        if not short:
            s = "parcours " if lower else "Parcours "
        s += Printer.elegantjoin(sorted([x.letter for x in t]))
        return s

    def getCompLevel(self, year=None):
        a = set()
        for t in self:
            a = a | t.getCompLevel(year=year)
        return a

    def getExpandedSet(self):
        a = set()
        for x in self:
            a = a | x.getExpandedSet()
        return ParcoursSet(a)

    def isPlural(self):
        if len(self) > 1:
            return 2
        for x in self:
            return x.isPlural()
        return 1


class Module(SmartObject):
    def _add_coeff(self, id, d, backref=None, namespace=None):
        return Coefficient(id, d, backref=backref, namespace=namespace)

    def getParcours(self):
        return ParcoursSet(self.parcours.values())

    def getParcoursBin(self):
        a = set()
        for p in self.parcours.values():
            b = [x.letter for x in p.getExpandedSet()]
            a = a | set(b)
        return "".join(sorted(list(b)))

    def getAC(self, subcomp=None):
        a = set(self.ac.values())
        if subcomp == None:
            return a
        b = set()
        for x in a:
            if x.parent == subcomp:
                b.add(x)
        return b

    def getCoeff(self, comp=None):
        if comp == None:
            return CoefficientSet(self.coeff.values())
        a = set()
        for c in self.coeff.values():
            u = c.ue
            # UE => NiveauCompetence => Competence
            if u.parent.parent == comp:
                a.add(c)
        return CoefficientSet(a)

    def getUE(self, comp=None):
        return {x.ue for x in self.getCoeff(comp=comp)}

    def getNiveauCompetence(self, comp=None):
        b = set()
        ac = self.ac.values()
        for x in ac:
            b.add(x.parent)
        return b

    def getCanonical(self, lower=True):
        return self.id + " " + self.getName()

    def getShortCanonical(self, lower=True):
        return self.id + " " + self.getShortname()

    def getShortId(self):
        return re.sub("[^A-Z0-9a-z]", "", self.id)


class ModuleList(list):
    def getParcoursBin(self):
        a = {}
        for m in self:
            b = m.getParcoursBin()
            if b in a:
                a[b].add(m)
            else:
                a[b] = {m}
        return a

    def getParcoursBinBasic(self):
        a = set()
        for m in self:
            a.add(m.getParcoursBin())
        unbroken = False
        while not unbroken:
            newa = {x for x in a}
            unbroken = True
            for x in newa:
                if not unbroken:
                    break
                for y in newa:
                    if not unbroken:
                        break
                    if x == y:
                        continue
                    xset = {e for e in x}
                    yset = {e for e in y}
                    if xset & yset:
                        unbroken = False
                        a.remove(x)
                        a.remove(y)
                        if xset - yset:
                            a.add("".join(sorted(list(xset - yset))))
                        if yset - xset:
                            a.add("".join(sorted(list(yset - xset))))
                        if xset & yset:
                            a.add("".join(sorted(list(yset & xset))))
        return a


class Ressource(Module):
    class_props = ["keywords", "name", "shortname", "sem"]
    class_arrayprops = ["discipline", "topic", "description"]
    class_subs = ["learning", "coeff"]
    class_fkeys = ["ac", "parcours", "prerequisite"]

    def _add_learning(self, id, d, backref=None, namespace=None):
        return Savoir(id, d, backref=backref, namespace=namespace)

    def moduleType(self):
        return "2"

    def getDiscipline(self):
        return [[y.strip() for y in x.split(";")] for x in self.discipline]


class Savoir(SmartObject):
    class_arrayprops = ["topic"]


class Coefficient(SmartObject):
    class_props = ["value"]
    class_singlefkey = ["ue"]


class CoefficientSet(set):
    def sum(self):
        a = 0
        for x in self:
            a += int(x.value)
        return a


class SAE(Module):
    class_props = ["guideline", "name", "shortname", "sem"]
    class_arrayprops = ["description", "production"]
    class_subs = ["coeff", "model"]
    class_fkeys = ["ac", "parcours", "ress", "target"]

    def _add_model(self, id, d, backref=None, namespace=None):
        return SAEModel(id, d, backref=backref, namespace=namespace)

    def moduleType(self):
        return "0"


class SAEModel(SmartObject):
    class_props = ["name", "number", "format"]
    class_arrayprops = ["description", "evaluation", "objective", "synopsis"]


class Portfolio(Module):
    class_props = ["name", "shortname", "sem"]
    class_arrayprops = ["description"]
    class_subs = ["coeff"]
    class_fkeys = ["ac", "parcours", "ress"]

    def moduleType(self):
        return "1"


class Source(SmartObject):
    class_props = ["name", "shortname"]


class Hours(SmartObject):
    class_props = ["type", "value"]
    class_singlefkey = ["destination", "source"]


class HoursSet(set):
    def sum(self, onlyType=None, destination=None, source=None):
        a = 0.0
        for x in self:
            if onlyType == None or x.type in onlyType:
                if destination == None or destination == x.destination:
                    if source == None or source == x.source:
                        a += float(x.value)
        return a

    def sources(self, onlyType=None):
        a = set()
        for x in self:
            if onlyType == None or x.type in onlyType:
                a.add(x.source)
        return a

    def destinations(self, onlyType=None):
        a = set()
        for x in self:
            if onlyType == None or x.type in onlyType:
                a.add(x.destination)
        return a


class ReaderCSV:
    def __init__(self, path):
        self.objects = {}
        self.path = path

    def addrow(self, row):
        parent = row[0]
        parentkey = row[1]
        id = row[2]
        infotype = row[3]
        value = row[4]
        order = row[5]
        if order != "":
            order = int(order)
        if id not in self.objects:
            self.objects[id] = {}
            self.objects[id]["parent"] = parent
            self.objects[id]["parentkey"] = parentkey
            self.objects[id]["id"] = id
        else:
            if (
                self.objects[id]["parent"] != parent
                or self.objects[id]["parentkey"] != parentkey
            ):
                raise Exception(
                    "Data inconsistent : two entries with id {} and differing parenthood ({},{}) and ({},{}).".format(
                        id,
                        parent,
                        parentkey,
                        self.objects[id]["parent"],
                        self.objects[id]["parentkey"],
                    )
                )
        if order == "":
            if infotype in self.objects[id]:
                raise Exception(
                    "Data inconsistent : two entries with id {}, infotype {} and two values {} and {}.".format(
                        id, infotype, value, self.objects[id][infotype]
                    )
                )
            else:
                self.objects[id][infotype] = value
        else:
            if infotype not in self.objects[id]:
                self.objects[id][infotype] = []
            x = self.objects[id][infotype]
            if order < 0:
                raise Exception(
                    "Data inconsistent : Entry with id {}, infotype {} and non-strictly-positive order {}.".format(
                        id, infotype, value, order
                    )
                )
            if len(x) == order - 1:
                self.objects[id][infotype].append(value)
            elif len(x) > order - 1:
                if self.objects[id][infotype][order - 1] != None:
                    raise Exception(
                        "Data inconsistent : Entry with id {}, infotype {} and order {} already has value {}.".format(
                            id, infotype, order, self.objects[id][infotype][order - 1]
                        )
                    )
                self.objects[id][infotype][order - 1] = value
            elif order < 100:  # protection
                self.objects[id][infotype] = [
                    x[i] if i < len(x) else None for i in range(0, order)
                ]
                self.objects[id][infotype][order - 1] = value
            else:
                raise Exception("Order is too large ({})".format(order))

    def readDataFromFile(self, filename):
        with open(filename) as csvfile:
            data = csv.reader(csvfile, delimiter="\t", quotechar='"')
            linecount = 0
            for row in data:
                linecount += 1
                if linecount == 1:
                    continue
                if row[0] == "":
                    continue
                self.addrow(row)

    def readData(self):
        for filename in [
            "Referentiel",
            "Competence",
            "CompositeCompetence",
            "NiveauCompetence",
            "ApprentissageCritique",
            "Parcours",
            "CompositeParcours",
            "UE",
            "Ressource",
            "Savoir",
            "SAE",
            "SAEModel",
            "Portfolio",
            "Source",
            "Horaires",
            "Coeff",
        ]:
            self.readDataFromFile(os.path.join(self.path, filename + ".tsv"))
        return self

    def output(self):
        d = {}
        for x in self.objects:
            xx = self.objects[x]
            xp = xx["parent"]
            xpk = xx["parentkey"]
            del xx["parent"]
            del xx["parentkey"]
            if xp != "/":
                if xpk not in self.objects[xp]:
                    self.objects[xp][xpk] = {}
                self.objects[xp][xpk][x] = xx
            else:
                if xpk not in d:
                    d[xpk] = {}
                d[xpk][x] = xx
        return [d["all"][x] for x in d["all"]][0]
