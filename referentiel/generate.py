#!/usr/bin/python3

import sys,os,re
import shutil
import csv
import subprocess
import math
import jinja2
import os
from jinja2 import Template
from locale import atof, setlocale, LC_NUMERIC
setlocale(LC_NUMERIC, 'C')
from collections import deque

doc=None

latexconv = {
    '&': r'\&',
    '%': r'\%',
    '$': r'\$',
    '#': r'\#',
    '_': r'\_',
    '{': r'\{',
    '}': r'\}',
    '~': r'\textasciitilde{}',
    '^': r'\^{}',
    '\\': r'\textbackslash{}',
    '<': r'\textless{}',
    '>': r'\textgreater{}',
}
latexre = re.compile('|'.join(re.escape(str(key)) for key in sorted(latexconv.keys(), key = lambda item: - len(item))))


def fmt2array(a):
    st=a
    r=[]
    store=''
    x=re.match(r'^([^`]*)`([^`]*)`(.*)$',st)
    while (x):
        if len(x.group(2))>0:
            r.append(store+x.group(1))
            r.append(x.group(2))
        else:
            store += x.group(1)
            store += '`'
        st=x.group(3)
        x=re.match(r'^([^`]*)`([^`]*)`(.*)$',st)
    r.append(store+st)
    return r
def formatObjects(a,objlist,toFloat=False):
    fmt=fmt2array(a)
    res=[str(fmt[0])]*len(objlist)
    for i in range(0,len(fmt)//2):
        for j in range(0,len(objlist)):
            m=getattr(objlist[j],fmt[2*i+1])
            res[j]+=str(m())
            res[j]+=fmt[2*i+2]
    if toFloat:
        return([float(x) for x in res])
    return(res)

def LaTeXEscape(a):
    """
        :param text: a plain text message
        :return: the message escaped to appear correctly in LaTeX
    """
    global latexre,latexconv
    if isinstance(a,list):
        b=[]
        for x in a:
            b.append(latexre.sub(lambda match: latexconv[match.group()], x))
        return b
    elif isinstance(a,str):
        return latexre.sub(lambda match: latexconv[match.group()], a)
    else:
        return a

def elegantjoin(ll):
    l=list(ll)
    if len(l)==0:
        return ''
    if len(l)==1:
        return(l[0])
    return ', '.join([str(x) for x in l[0:-1]])+' et '+str(l[-1])

def merge(l):
    r=[]
    for i in l:
        for j in i:
            r.append(j)
    return(r)

def hours2string(a):
    if isinstance(a,str):
        a=float(a)
    hour=math.floor(a)
    minu=math.floor(a*60-hour*60)
    if minu>9:
        return '{0}h{1}'.format(hour,minu)
    elif minu>0:
        return '{0}h0{1}'.format(hour,minu)
    return str(hour)+'h'
def hours2num(a):
    if a==0:
        return ''
    hour=math.floor(a)
    minu=math.floor(100*(a*60-hour*60))
    if minu>9:
        return '{0},{1}'.format(hour,minu)
    elif minu>0:
        return '{0},0{1}'.format(hour,minu)
    return str(hour)

def doublehour(a,b,double='{0} (dont {1} de TP)',simple='{0}'):
    if (b>0):
        return double.format(hours2string(a),hours2string(b))
    return simple.format(hours2string(a))    

def semestre2year(a):
    idx=(int(a)+1)//2
    if idx>0 and idx<4:
        return idx
    raise Exception('Key '+str(int(idx))+' out of range')
def year2semestre(a):
    idx=(int(a))
    if idx>0 and idx<4:
        return [str(idx*2-1),str(idx*2)]
    raise Exception('Key '+str(int(idx))+' out of range')

def copyAssets(inpath,out):
    if not os.path.exists(inpath):
        return 0
    files = os.listdir(inpath)
    c=0
    for file in files:
        ffile = os.path.join(inpath, file)
        if os.path.isfile(ffile):
            c+=1
            shutil.copy(ffile, out)
    return c

def sumCoeffs(array,**args):
    a=0.0
    for c in array:
        if 'module' in args:
            x=c.getCoeff(args['module'])
            if x != None:
                a+=float(x[1])
        else:
            a+=float(c.getCoeffs(**args)[1])
    return(a)

utils={'formatObjects':formatObjects,'semestre2year':semestre2year,'sumCoeffs': sumCoeffs}

class Printer:
    def __init__(self,REF,mode):
        self.queue=deque()
        self.done=deque()
        self.REF=REF
        self.path=os.path.abspath(os.path.join('.',mode))
        self.outpath=os.path.abspath(os.path.join('.','output',mode))
        if not os.path.exists(self.outpath):
            os.makedirs(self.outpath)
        self._specific()
        self.jinja_env.filters['elegantjoin']=elegantjoin
        self.jinja_env.filters['le']=LaTeXEscape
        self.jinja_env.filters['hours']=hours2string
        self.jinja_env.filters['hoursnum']=hours2num
        self.jinja_env.filters['merge']=merge
    def _specific(self):
        pass
    def addTemplate(self,name,subjectstring,dictionary={}):
        self.queue.append([name,subjectstring,dictionary])
        return True
    def runOne(self):
        global utils
        if not self.queue:
            return False
        one=self.queue.popleft()
        onebase=one[0]
        onebasestripped=re.sub(self.suffix,'',onebase)
        onesubject=one[1]
        oneversion=self.REF.getShortVersion()
        onedict=one[2]
        filename=self.REF.getShortId()+'_'+onebasestripped+'_'+str(onesubject)+'_'+oneversion+self.suffix
        outpath=os.path.join(self.outpath,filename)
        onedict['data']=self.REF
        onedict['subject']=onesubject
        onedict['utils']=utils
        onedict['printer']=self
        with open(outpath,"w") as f:
            template = self.jinja_env.get_template(onebase)
            output=template.render(**onedict)
            print(output,file=f)
        return outpath
    def run(self):
        self.prologue()
        while self.queue:
            done=self.runOne()
            self.done.append(done)
            print(done)
        self.epilogue()
    def prologue(self):
        outassets=os.path.join(self.outpath,'assets')
        if not os.path.exists(outassets):
            os.makedirs(outassets)
        inassets=os.path.abspath(os.path.join('.','assets'))
        copyAssets(inassets,outassets)
        inassets=os.path.abspath(os.path.join(self.path,'assets'))
        copyAssets(inassets,outassets)
    def epilogue(self):
        pass

class LaTeXPrinter(Printer):
    def _specific(self):
        self.suffix='.tex'
        self.jinja_env = jinja2.Environment(
	    block_start_string = '\BLOCK{',
	    block_end_string = '}',
	    variable_start_string = '\VAR{',
	    variable_end_string = '}',
	    comment_start_string = '\#{',
	    comment_end_string = '}',
	    line_statement_prefix = '%%',
	    line_comment_prefix = '% #',
	    trim_blocks = True,
	    autoescape = False,
	    loader = jinja2.FileSystemLoader(self.path)
        )
    def epilogue(self):
        for texfile in self.done:
            wd = os.getcwd()
            dirname=os.path.dirname(texfile)
            os.chdir(dirname)
            subprocess.check_call(["lualatex",texfile])
            logfile=texfile[0:-3]+'log'
            rerun=False
            with open(logfile) as log:
                for x in log.readlines():
                    if x[0:47]=='LaTeX Warning: Label(s) may have changed. Rerun':
                        rerun=True
            if (rerun):
                subprocess.check_call(["lualatex",texfile])
            os.chdir(wd)
class HTMLPrinter(Printer):
    def _specific(self):
        self.suffix='.html'
        self.jinja_env = jinja2.Environment(
	    trim_blocks = True,
	    loader = jinja2.FileSystemLoader(self.path)
        )
        

class DataBlob:
    _blob="DataBlob"
    def __init__(self,id: str):
        self.data={}
        self.print={}
        self.id=id
    def __str__(self):
        return '<Object '+type(self)._blob+' '+str(self.id)+'>'
    def getId(self):
        return self.id
    def getShortId(self):
        return re.sub(r'[- ._]','',self.id)
    def isPlural(self):
        return 1
    def addInfo(self,infotype: str,infovalue):
        if infotype not in self.data:
            self.data[infotype]=[infovalue]
        else:
            self.data[infotype].append(infovalue)
    def _getData(self,k: str,idx=None,fail=False):
        if k not in self.data:
            if fail:
                raise Exception('Key '+k+' not found in '+str(self))
            else:
                return []
        if idx==None:
            return self.data[k]
        if int(idx)<0 or int(idx)>=len(self.data[k]):
            if fail:
                raise Exception('Key '+str(int(idx))+' out of range '+str(self)+'['+k+']')
            else:
                return None
        else:
            return self.data[k][int(idx)]

class DataBlobAsDict(DataBlob):
    def addInfo(self,infotype: str,infokey: str,infovalue):
        if infotype not in self.data:
            self.data[infotype]={infokey:infovalue}
        else:
            self.data[infotype][infokey]=infovalue
    def _getData(self,k: str,idx=None,fail=False):
        if k not in self.data:
            if fail:
                raise Exception('Key '+k+' not found in '+str(self))
            else:
                return {}
        if idx==None:
            return self.data[k]
        if idx not in self.data[k]:
            if fail:
                raise Exception('Key '+idx+' not found in '+str(self)+'['+k+']')
            else:
                return None
        return self.data[k][idx]


class Comp(DataBlobAsDict):
    _blob='Comp'
    def __init__(self,id: str):
        super().__init__(id)
        self.ac=[]
        self.coeffs={}
    def getNum(self):
        try:
            return self._getData('numero',idx='code',fail=True)
        except Exception:
            return '?'
    def getShorttxt(self):
        if 'activite' in self.data:
            if 'activiteshort' in self.data['activite']: 
                return self.data['activite']['activiteshort']
            elif 'activite' in self.data['activite']:
                return self.data['activite']['activite']
        return '[?'+self.id+'?]'
    def getLongtxt(self):
        if 'activite' in self.data:
            if 'activite' in self.data['activite']: 
                return self.data['activite']['activite']
            elif 'activiteshort' in self.data['activite']:
                return self.data['activite']['activiteshort']
        return '[?'+self.id+'?]'
    def addAC(self,ac):
        self.ac.append(ac)
    def getDescriptionList(self):
        try:
            dictionary=self._getData('comptxt',fail=True)
            return [dictionary[x] for key in sorted(dictionary.keys())]
        except Exception:
            return '(pas de description disponible)'
    def getNiveauDict(self,year: int):
        if year>0 and year<4:
            return self._getData('niveau'+str(year),fail=True)
        raise Exception('Year {} is out of range'.format(year))
    def getNiveau(self,year: int ,k: str):
        if year>0 and year<4:
            return self._getData('niveau'+str(year),idx=k,fail=True)
        raise Exception('Year {} is out of range'.format(year))
    
    def getACObjects(self,semestre=None,year=None):
        if semestre==None and year==None:
            return self.ac
        a=[]
        if semestre != None:
            year=semestre2year(semestre)
        for ac in self.ac:
            if int(ac.getLevel())==year:
                a.append(ac)
        return a
class NormalComp(Comp):
    def _isNormal(self):
        return True
    def addCoeff(self,moduleobj,value):
        self.coeffs[moduleobj.getId()]=(moduleobj,value)
    def getCoeff(self,moduleobj):
        if moduleobj.getId() in self.coeffs:
            return self.coeffs[moduleobj.getId()]
        return None
    def getCoeffs(self,semestre=None,onlyType=None):
        if 'RESS' in onlyType:
            ressources=True
        else:
            ressources=False
        if 'SAE' in onlyType:
            sae=True
        else:
            sae=False
        if 'PORTFOLIO' in onlyType:
            portfolio=True
        else:
            portfolio=False
        a=0
        b=[]
        for i in self.coeffs:
            module=self.coeffs[i][0]
            value=self.coeffs[i][1]
            if semestre!=None and semestre not in module.getSemestreList():
                continue
            if module.subtype()==Module.SUBTYPE_RESS and ressources:
                a+=int(value)
                b.append(module)
            if module.subtype()==Module.SUBTYPE_SAE and sae:
                a+=int(value)
                b.append(module)
            if module.subtype()==Module.SUBTYPE_PORTFOLIO and portfolio:
                a+=int(value)
                b.append(module)
        return (b,a)
class TransversalComp(Comp):
    def __init__(self):
        super().__init__('TRANSVERSAL')
        self.data['numero']={'code': '*'}
    def isPlural(self):
        return 2
    def getLongtxt(self):
        return 'Toutes les compétences'
    def getShorttxt(self):
        return 'Transversal'
    def getNiveauDict(self,year: int):
        if year>0 and year<4:
            return {'niveau'+str(year):''}
        raise Exception('Year {} is out of range'.format(year))


class AC(DataBlob):
    def __init__(self,id: str,comp: Comp):
        self.id=id
        self.compref=comp
        self.txt=None
        self.level=None
        comp.addAC(self)
        self.data={}
    def addInfo(self,code,value):
        if (code=='ac'):
            self.txt=value
            self.short=re.sub(r" *\([^)]*\)", "", value)
        elif (code=='acnum'):
            self.num=value
        elif (code=='aclevel'):
            self.level=value
        else:
            # Unknown code, forward compatibility
            self.data[code]=value
    def getLongtxt(self):
        return self.short
    def getShorttxt(self):
        return self.short
    def getCompId(self):
        return self.compref.getId()
    def getCompNum(self):
        return self.compref.getNum()
    def getCompObject(self):
        return self.compref
    def getLevel(self):
        return self.level
    def getNum(self):
        return self.num
    def getShortonly(self):
        return self.short
class TransversalAC(AC):
    def __init__(self,comp):
        super().__init__('TRANSVERSAL',comp)
        self.addInfo('acnum',0)
        self.addInfo('ac','Tous les apprentissages critiques (enseignement transversal)')
    def isPlural(self):
        return 2
    def getLongtxt(self,level=False):
        return 'Tous les apprentissages critiques (enseignement transversal)'
    def getShorttxt(self,level=False):
        return 'Tous les apprentissages critiques'


class Referentiel:
    def debug(self,a):
        print(str(a))
    def __init__(self,name: str=None,shortname=None):
        self.name=name
        self.shortname=name
        if shortname != None:
            self.shortname=name
        self.version=''
        self.COMP={}
        self.PARCOURS={}
        self.SAE={}
        self.RESS={}
        self.AC={}
        self.PORTFOLIO={}
        self.HOURS={}
        self.COMP['TRANSVERSAL']=TransversalComp()
        self.AC['TRANSVERSAL']=TransversalAC(self.COMP['TRANSVERSAL'])
        self.introduction={}
        self.introductionparcours={}
        self.introductionparcoursref={}
        self.printer=[]
        self.PORTFOLIOCODES=[]
    def addTroncCommun(self,id: str):
        self.PARCOURS[id]=ParcoursCommun(id,self.PARCOURS)
    def getId(self):
        return self.name
    def getShortId(self):
        return re.sub(r'[^a-zA-Z0-9]','',self.shortname)
    def getVersion(self):
        return self.version
    def getShortVersion(self):
        x=re.match(r'^([.A-Za-z0-9]*).*$',self.version)
        if x:
            return x.group(1)
        else:
            return self.version
    def getNumber(self):
        return self.number
    def getHoursBlock(self,k,fail=False):
        if k not in self.HOURS:
            if fail:
                raise Exception('Source {} not found'.format(k))
            self.HOURS[k]=Source(k)
        return self.HOURS[k]
    def getHoursBlockList(self):
        return self.HOURS.values()
    def getComp(self,k,fail=False):
        if k not in self.COMP:
            if fail:
                raise Exception('Comp {} not found'.format(k))
            self.COMP[k]=NormalComp(k)
        return self.COMP[k]
    def getNormalCompList(self):
        a=[]
        for x in self.COMP:
            if isinstance(self.COMP[x],NormalComp):
                a.append(self.COMP[x])
        return(a)

    def getSAE(self,k,fail=False):
        if k not in self.SAE:
            if fail:
                raise Exception('SAE {} not found'.format(k))
            self.SAE[k]=SAE(k)
        return self.SAE[k]
    def getPortfolio(self,k,fail=False):
        if k not in self.PORTFOLIO:
            if fail:
                raise Exception('Portfolio {} not found'.format(k))
            self.PORTFOLIO[k]=Portfolio(k)
        return self.PORTFOLIO[k]
    def getAC(self,k,comp=None,fail=False):
        if k not in self.AC:
            if fail or comp==None:
                raise Exception('Unknown AC ({})'.format(k))
            else:
                compObject=self.getComp(comp,fail)
                self.AC[k]=AC(k,compObject)
        return self.AC[k]
    def getACList(self):
        return self.AC.values()
    def getRessource(self,k,fail=False):
        if k not in self.RESS:
            if fail:
                raise Exception('Ressource {} not found'.format(k))
            self.RESS[k]=Ressource(k)
        return self.RESS[k]
    def getModuleObjects(self,onlyType=None,semestre=None,year=None,parcours=None,interparcours=None):
        r=set()
        all=set(self.RESS.values())|set(self.SAE.values())|set(self.PORTFOLIO.values())
        if onlyType==None:
            r=all
        else:
            for t in onlyType:
                if t=='SAE':
                    r=r.union(self.SAE.values())
                if t=='RESS':
                    r=r.union(self.RESS.values())
                if t=='PORTFOLIO':
                    r=r.union(self.PORTFOLIO.values())
        if year!=None or semestre!=None:
            sems=[]
            if year!=None:
                sems=year2semestre(year)
            elif semestre!=None:
                sems=[semestre]
            filtered=set()
            for sem in sems:
                filtered=filtered|{x for x in r if sem in x.getSemestreList()}
            r=filtered
        if parcours!=None or interparcours!=None:
            parc=set()
            if interparcours!=None:
                parc={x for x in self.PARCOURS.values() if interparcours.intersects(x)}
            if parcours!=None:
                parc={parcours}
            filtered=set()
            for p in parc:
                filtered=filtered|{x for x in r if p in x.getParcoursObjects()}
            r=filtered
        return list(sorted(r,key=lambda x:(("0" if x in self.SAE else "1")+x.getId())))
    def getRessourceObjects(self,**args):
        return self.getModuleObjects(onlyType=['RESS'],**args)
    def getSAEObjects(self,**args):
        return self.getModuleObjects(onlyType=['SAE'],**args)
    def getPortfolioObjects(self,**args):
        return self.getModuleObjects(onlyType=['PORTFOLIO'],**args)
    def getParcours(self,k,fail=False):
        if k not in self.PARCOURS:
            if fail:
                raise Exception('Parcours {} not found'.format(k))
            self.PARCOURS[k]=Parcours(k)
        return self.PARCOURS[k]
    def getParcoursObjects(self,all=False,semestre=None,year=None,forceNormal=False,parcours=None,interparcours=None):
        if all:
            if forceNormal:
                return sorted([x for x in self.PARCOURS.values() if x.isNormal()],key=lambda x:x.getId())
            else:
                return sorted(self.PARCOURS.values(),key=lambda x:x.getId())
        sm=self.getModuleObjects(semestre=semestre,year=year,parcours=parcours,interparcours=interparcours)
        parc=set()
        for m in sm:
            parc=parc|set(m.getParcoursObjects())
        if forceNormal:
            parcn=set([x for x in parc if x.isNormal()])
            for p in [x for x in parc if not x.isNormal()]:
                parcn=parcn|p.getExpandedSet()
            parc=parcn
        return sorted(list(parc),key=lambda x:((str(x.isPlural()+1) if x.isNormal() else '9')+x.getId()))
            
    def updateObjects(self):
        for r in self.RESS.values():
            for a in r.getACList():
                r.addInfo('acobject',self.getAC(a,fail=True))
            for a in r.getParcoursList():
                r.addInfo('parcoursobject',self.getParcours(a,fail=True))
            for a in r.getPrerequisList():
                r.addInfo('prerequisobject',self.getRessource(a,fail=True))
        for s in self.SAE.values():
            for a in s.getACList():
                s.addInfo('acobject',self.getAC(a,fail=True))
            for a in s.getParcoursList():
                s.addInfo('parcoursobject',self.getParcours(a,fail=True))
            for a in s.getCompList():
                s.addInfo('cibleobject',self.getComp(a,fail=True))
            for a in s.getRessourceList():
                s.addInfo('ressobject',self.getRessource(a,fail=True))
        for s in self.PORTFOLIO.values():
            for a in r.getACList():
                s.addInfo('acobject',self.getAC(a,fail=True))
            for a in r.getParcoursList():
                s.addInfo('parcoursobject',self.getParcours(a,fail=True))
            for a in s.getRessourceList():
                s.addInfo('ressobject',self.getRessource(a,fail=True))
    def getSemestres(self,year=None):
        sems={}
        for r in []+list(self.getRessourceObjects())+list(self.getSAEObjects()):
            semestres=r.getSemestreList()
            for s in semestres:
                if year==None or int(semestre2year(s))==int(year):
                    sems[s]=1
        return list(sems.keys())
    def getYears(self):
        sems={}
        for r in []+list(self.getRessourceObjects())+list(self.getSAEObjects()):
            semestres=r.getSemestreList()
            for s in semestres:
                sems[semestre2year(s)]=1
        return list(sems.keys())
    def getPossibleCompObjects(self,parcoursList,year):
        nivset=set()
        for p in parcoursList:
            nivset=nivset.union(set(p.getComps(year)))
        niveaux=sorted(list(nivset))
        out=[]
        for n in niveaux:
            for c in self.getNormalCompList():
                if n in c.getNiveauDict(year):
                    out.append(c)
        return out
    def sumIn(self,moduleList,infotype=None):
        a=0.0
        for mm in moduleList:
            m=mm
            if isinstance(mm,DataBlob):
                m=mm.getId()
            if m in self.HOURS:
                msource=self.HOURS[m]
                a+=msource.sumIn(infotype=infotype)
        return a

    def sumOut(self,moduleList,infotype=None):
        a=0.0
        for mm in moduleList:
            m=mm
            if isinstance(mm,DataBlob):
                m=mm.getId()
            if m in self.HOURS:
                msource=self.HOURS[m]
                a+=msource.sumOut(infotype=infotype)
        return a

    def addCoeff(self,moduleid,compid,value):
        if compid not in self.COMP:
            raise Exception('Coefficient with bad CompId {}'.format(compid))
        comp=self.COMP[compid]
        module=None
        if moduleid not in self.RESS and moduleid not in self.SAE and moduleid not in self.PORTFOLIO:
            raise Exception('Coefficient with bad ModuleId {}'.format(moduleid))
        elif moduleid in self.SAE:
            module=self.SAE[moduleid]
        elif moduleid in self.PORTFOLIO:
            module=self.PORTFOLIO[moduleid]
        else:
            module=self.RESS[moduleid]
        module.addCoeff(comp,value)
        comp.addCoeff(module,value)

    def getIntroductionList(self):
        a=[]
        for x in sorted(self.introduction.keys()):
            a.append(self.introduction[x])
        return a
    def getIntroductionParcours(self):
        a=[]
        for p in sorted(self.introduction.keys()):
            b=[self.introductionparcours[p],self.PARCOURS[self.introductionparcoursref[p]]]
            a.append(b)
        return a
            
    def getParcoursCanonical(self,plist,lower=True):
        pris=set()
        liste=plist
        if isinstance(plist,Parcours):
            liste=[plist]
        if len(liste)==1:
            return liste[0].getCanonical(lower)
        for p in liste:
            pris=pris|p.getExpandedSet()
        for p in self.PARCOURS.values():
            expansion=p.getExpandedSet()
            if len(pris&expansion)==len(pris) and len(pris)==len(expansion):
                return p.getCanonical(lower)
        if lower:
            s='parcours '
        else:
            s='Parcours '
        s+=elegantjoin(sorted([x.getLettreList()[0] for x in pris]))
        return(s)
        
class Source:
    def __init__(self,id):
        self.data={'in':{},'out':{}}
        self.id=id
    def __str__(self):
        return '<Object Source '+self.id+'>'
    def addHoursIn(self,infotype,source,info_value):
        if infotype not in self.data['in']:
            self.data['in'][infotype]={}
        if source not in self.data['in'][infotype]:
            self.data['in'][infotype][source]=0
            self.data['in'][infotype][source]+=info_value
    def addHoursOut(self,infotype,destination,info_value):
        if infotype not in self.data['out']:
            self.data['out'][infotype]={}
        if destination not in self.data['out'][infotype]:
            self.data['out'][infotype][destination]=0
            self.data['out'][infotype][destination]+=info_value
    def sumOut(self,infotype=None,destination=None):
        return self._sumFilter(self.data['out'],infotype,destination)
    def listOut(self,infotype=None,destination=None):
        return self._listFilter(self.data['out'],infotype,destination)
    def sumIn(self,infotype=None,source=None):
        return self._sumFilter(self.data['in'],infotype,source)
    def listIn(self,infotype=None,source=None):
        return self._listFilter(self.data['in'],infotype,source)
    def _listFilter(self,data,infotype,partner):
        r={}
        for xtype in data:
            if infotype != None and xtype not in infotype:
                continue
            for xpartner in data[xtype]:
                if partner != None and xpartner not in partner:
                    continue
                if data[xtype][xpartner]>0:
                    r[xpartner]=1
        return(list(r.keys()))
    def _sumFilter(self,data,infotype,partner):
        r=0.0
        for xtype in data:
            if infotype != None and xtype not in infotype:
                continue
            for xpartner in data[xtype]:
                if partner != None and xpartner not in partner:
                    continue
                r += data[xtype][xpartner]
        return(r)


class Module(DataBlob):
    _blob='Module'
    SUBTYPE_SAE='SAE'
    SUBTYPE_RESS='RESS'
    SUBTYPE_PORTFOLIO='PORTFOLIO'
    def __init__(self,id):
        super().__init__(id)
        self.coeffs=[]
    def getShorttxt(self):
        txt='???'
        if 'shortname' in self.data:
            txt=self.data['shortname'][0]
        elif 'longname' in self.data:
            txt=self.data['longname'][0]
        return txt
    def getLongtxt(self):
        txt='???'
        if 'longname' in self.data:
            txt=self.data['longname'][0]
        elif 'shortname' in self.data:
            txt=self.data['shortname'][0]
        return txt
    def getSemestreList(self):
        return self._getData('semestre')
    def getParcoursList(self):
        return self._getData('parcours')
    def getParcoursObjects(self):
        return self._getData('parcoursobject')
    def getACList(self):
        return self._getData('ac')
    def getACObjects(self,comp=None):
        if comp==None:
            return sorted(self._getData('acobject'),key=lambda x:x.getNum())
        cid=comp.getId()
        return sorted([x for x in self._getData('acobject') if x.getCompId()==cid],key=lambda x:x.getNum())
    def getDescriptionList(self):
        return self._getData('desc')
    def addCoeff(self,compobj,value):
        self.coeffs.append((compobj,value))
        

class SAE(Module):
    _blob='SAE'
    def __init__(self,id):
        super().__init__(id)
        self.exemple={}
        # Specific to SAE : Comp, Preco, Ressource, Livrable, Exemples
    def subtype(self):
        return Module.SUBTYPE_SAE
    def getCompList(self):
        return self._getData('cible')
    def getCompObjects(self):
        return self._getData('cibleobject')
    def getPrecoList(self):
        return self._getData('preco')
    def getRessourceList(self):
        return self._getData('ress')
    def getRessourceObjects(self):
        return self._getData('ressobject')
    def getLivrableList(self):
        return self._getData('livrable')
    def getExemple(self,order):
        if order not in self.exemple:
            self.exemple[order]=ExempleSAE(self.id,order)
        return self.exemple[order]
    def getExemples(self):
        r=list(self.exemple.keys())
        r.sort()
        return r
    def getExempleObjects(self):
        r=list(self.exemple.keys())
        r.sort()
        return [self.exemple[x] for x in r]

class Portfolio(SAE):
    _blob='PORTFOLIO'
    def subtype(self):
        return Module.SUBTYPE_PORTFOLIO

class ExempleSAE(DataBlob):
    def __init__(self,sae_id,id):
        super().__init__(id)
        self.sae_id=sae_id
    def getSynopsis(self):
        return self._getData('synopsis')
    def getProb(self):
        return self._getData('prob')
    def getForm(self):
        return self._getData('form')
    def getDesc(self):
        return self._getData('form')
    def getEval(self):
        return self._getData('eval')
    def getTitre(self):
        return self._getData('titre')[0]


class Ressource(Module):
    _blob="Ressource"
    # Specific to Ressource : Prerequis, Keywords, Objectif, Savoirs
    def subtype(self):
        return Module.SUBTYPE_RESS
    def getPrerequisList(self):
        return self._getData('prerequis')
    def getPrerequisObjects(self):
        return sorted(self._getData('prerequisobject'),key=lambda x:x.getId())
    def getKeywordsList(self):
        return self._getData('keywords')
    def getObjectifList(self):
        return self._getData('objectif')
    def getSavoirsList(self):
        return self._getData('savoir')
    def getCoeffs(self):
        return self._getData('coeffs')
    def getCoeffs(self):
        return self._getData('coeffs')
    def getDisciplineList(self):
        d=self._getData('discipline')
        p=self._getData('pole')
        a=[]
        for i in range(0,len(d)):
            b=[d[i]]
            if i<len(p) and p[i] and p[i]!=d[i]:
                b.append(p[i])
            a.append(b)
        return a
            


class Parcours(DataBlob):
    def getCanonical(self,lower=True):
        if 'canonical' in self.data:
            if lower:
                s=self.data['canonical'][0][0].lower()
            else:
                s=self.data['canonical'][0][0].upper()
            return s+self.data['canonical'][0][1:]
        if lower:
            s='parcours '
        else:
            s='Parcours '
        return s+' '+self._getData('lettre')[0]
    def intersects(self,p):
        a=self.getLettreList()
        b=p.getLettreList()
        for x in a:
            if x in b:
                return True
        return False
    def isNormal(self):
        return True
    def getExpandedSet(self):
        return {self}
    def getLettreList(self):
        return self._getData('lettre')
    def getComps(self,year):
        if year==1:
            return self._getData('compa1')
        elif year==2:
            return self._getData('compa2')
        elif year==3:
            return self._getData('compa3')
        raise Exception('Year {} out of range'.format(year))

    def getNameList(self):
        return self._getData('nom')
    def getShorttxt(self):
        return 'parcours '+elegantjoin(self.getLettreList())
class ParcoursCommun(Parcours):
    def isPlural(self):
        return len(self.others)
    def isNormal(self):
        return False
    def getCanonical(self,lower=True):
        if lower:
            s=self.data['canonical'][0][0].lower()
        else:
            s=self.data['canonical'][0][0].upper()
        return s+self.data['canonical'][0][1:]
    def __init__(self,id,pdict,name="Tronc commun",canonical="tous parcours"):
        super().__init__(id)
        self.others=[]
        self.data['nom']=[name]
        self.data['canonical']=[canonical]
        for x in pdict:
            if pdict[x].isNormal():
                self.others.append(pdict[x])
    def getExpandedSet(self):
        return set(self.others)
    def getComps(self,year):
        a=set()
        for x in self.others:
            a=a.union(set(x.getComps(year)))
        return list(a)
    def getLettreList(self):
        t={}
        for x in self.others:
            for y in x.getLettreList():
                t[y]=1
                tt=list(t.keys())
                tt.sort()
        return tt

    
class ReaderCSV:
    def __init__(self,ref):
        self.REF=ref
    def readRowFromComp(self,row):
        infotype=row[1]
        compcode=row[0]
        code=row[2]
        value=row[3]
        comp=self.REF.getComp(compcode)
        if infotype in ['ac','aclevel', 'acnum']:
            self.REF.getAC(code,compcode).addInfo(infotype,value)
        else:
            comp.addInfo(infotype,code,value)
    def readRowFromParcours(self,row):
        rkey=row[0]
        infotype=row[1]
        value=row[2]
        self.REF.getParcours(rkey).addInfo(infotype,value)
    def readRowFromRess(self,row):
        resscode=row[0]
        infotype=row[1]
        value=row[2]
        self.REF.getRessource(resscode).addInfo(infotype,value)
    def readRowFromSavoirs(self,row):
        resscode=row[0]
        value=row[1]
        if len(resscode)>0:
            self.REF.getRessource(resscode,fail=True).addInfo('savoir',value)
    def readRowFromPortfolio(self,row):
        resscode=row[0]
        self.REF.PORTFOLIOCODES.append(resscode)
    def readRowFromCoeffs(self,row):
        resscode=row[0]
        infotype=row[1]
        comp=row[2]
        value=row[3]
        self.REF.addCoeff(resscode,comp,value)
    def readRowFromSAE(self,row):
        infotype=row[1]
        rkey=row[0]
        code=row[2]
        order=row[3]
        if rkey in self.REF.PORTFOLIOCODES:
            sae=self.REF.getPortfolio(rkey)
        else:
            sae=self.REF.getSAE(rkey)
        if infotype[0:7]=='exemple':
            if re.match(r'^[0-9]+$',order) and int(order)>0:
                exemple=sae.getExemple(order)
                exemple.addInfo(infotype[7:],code)
            else:
                raise Exception('No order for example ({})'.format(str(row)))
        elif len(rkey)>0:
            sae.addInfo(infotype,code)
    def readRowFromHoraires(self,row):
        nature=row[1]
        value=atof(row[2])
        source=row[0]
        destination=row[3]
        self.REF.getHoursBlock(source).addHoursOut(nature,destination,value)
        self.REF.getHoursBlock(destination).addHoursIn(nature,source,value)
    def readRowFromRef(self,row):
        key=row[0]
        value=row[1]
        order=row[2]
        if key=='name':
            self.REF.name=value
        if key=='shortname':
            self.REF.shortname=value
        if key=='version':
            self.REF.version=value
        if key=='number':
            self.REF.number=value
        if key=='introduction':
            self.REF.introduction[order]=value
        if key=='introductionparcours':
            self.REF.introductionparcours[order]=value
        if key=='introductionparcoursref':
            self.REF.introductionparcoursref[order]=value
        if key=='url':
            self.REF.url=value
    def readDataFromFile(self,filename,funcname):
        with open(filename) as csvfile:
            data = csv.reader(csvfile,delimiter='\t',quotechar='"')
            linecount=0
            func=getattr(self,funcname)
            for row in data:
                linecount+=1
                if linecount==1:
                    continue
                if row[0]=='':
                    continue
                func(row)
    def readData(self):
        self.readDataFromFile('BUT/REF.tsv','readRowFromRef')
        self.readDataFromFile('BUT/COMP.tsv','readRowFromComp')
        self.readDataFromFile('BUT/PORTFOLIO.tsv','readRowFromPortfolio')
        self.readDataFromFile('BUT/SAE.tsv','readRowFromSAE')
        self.readDataFromFile('BUT/Horaires.tsv','readRowFromHoraires')
        self.readDataFromFile('BUT/RESS.tsv','readRowFromRess')
        self.readDataFromFile('BUT/SAVOIRS.tsv','readRowFromSavoirs')
        self.readDataFromFile('BUT/PARCOURS.tsv','readRowFromParcours')
        self.readDataFromFile('BUT/COEFFS.tsv','readRowFromCoeffs')
        self.REF.addTroncCommun('TRONCCOMMUN')
        self.REF.updateObjects()


REF=Referentiel()
ReaderCSV(REF).readData()

jobs=[]
jobsn=0
for arg in sys.argv[1:]:
    x=re.match(r'^version=(.*)$',arg)
    if x:
        REF.version=x.group(1)
    else:
        files = os.listdir(os.path.join('.',arg))
        if files:
            if 'Referentiel.tex' in files:
                jobs.append((arg,'LaTeX','Referentiel.tex',REF.version))
            if 'Referentiel.html' in files:
                jobs.append((arg,'HTML','Referentiel.html',REF.version))
            jobsn+=1
if jobsn==0:        
    jobs=[('ACDI','LaTeX','Referentiel.tex')]

for arg in jobs:
    if arg[1]=='LaTeX':
        REF.version=arg[3]
        oneprinter=LaTeXPrinter(REF,arg[0])
        oneprinter.addTemplate(arg[2],REF.getId(),{})
        oneprinter.run()
    elif arg=='HTML':
        REF.version=arg[3]
        oneprinter=HTMLPrinter(REF,arg[0])
        oneprinter.addTemplate(arg[2],REF.getId(),{})
        oneprinter.run()

sys.exit(0)
