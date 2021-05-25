#!/usr/bin/python3
import but
import sys,os
import re

jobs=[]
currentversion='test'
currentdata='BUT'
currentoptions={}

for arg in sys.argv[1:]:
    x=re.match(r'^version=(.*)$',arg)
    if x:
        currentversion=x.group(1)
        continue
    x=re.match(r'^data=(.*)$',arg)
    if x:
        currentdata=x.group(1)
        continue
    found=False
    for popt in ['color','layout','margin']:
        x=re.match(r'^printer.'+popt+'=(.*)$',arg)
        if x:
            currentoptions[popt]=int(x.group(1))
            found=True
            continue
    if found:
        continue
    files = os.listdir(os.path.join('.',arg))
    if files:
        if 'Referentiel.tex' in files:
            jobs.append((arg,'LaTeX','Referentiel.tex',currentversion,currentdata,currentoptions.copy()))
        if 'Referentiel.html' in files:
            jobs.append((arg,'HTML','Referentiel.html',currentversion,currentdata,currentoptions.copy()))
        if 'Referentiel.json' in files:
            jobs.append((arg,'JSON','Referentiel.json',currentversion,currentdata,currentoptions.copy()))

if len(jobs)==0:
    jobs=[('ACDI','LaTeX','Referentiel.tex',currentversion,currentdata,currentoptions)]
    
REF=None
for arg in jobs:
    # Legacy format (bunch of Tab separated values)
    if os.path.isdir(arg[4]) and os.path.isfile(os.path.join(arg[4],'Referentiel.tsv')):
        x=but.ReaderCSV(arg[4])
        data=x.readData().output()
    else:
        # JSON format
        with open(arg[4]) as json_file:
            data = json.load(json_file)
    REF=but.Referentiel(data['id'],data)
    REF.dereferenceAll()
    if arg[3]!='test' or len(REF.version)==0:
        REF.version=arg[3]
    if arg[1]=='LaTeX':
        oneprinter=but.LaTeXPrinter(REF,arg[0])
    elif arg[1]=='HTML':
        oneprinter=but.HTMLPrinter(REF,arg[0])
    elif arg[1]=='JSON':
        oneprinter=but.JSONPrinter(REF,arg[0])
    for x in arg[5]:
        setattr(oneprinter,x,arg[5][x])
    oneprinter.addTemplate(arg[2],REF.getShortname(),{})
    oneprinter.run()

sys.exit(0)
