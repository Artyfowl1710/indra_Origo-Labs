from pathlib import Path
import sys,json,zipfile
ROOT=Path.cwd();sys.path.insert(0,str(ROOT/'indra/SIH-26'))
from indra_tools import docx,pdf,pptx,xlsx
out=ROOT/'data/test-results/documents';out.mkdir(parents=True,exist_ok=True)
md=out/'fixture.md';md.write_text('# Origo Test Report\n\nDisposable verification content.\n\n## Results\n\n- Revenue: 120\n- Cost: 80\n\n| Item | Value |\n| --- | --- |\n| Revenue | 120 |\n| Cost | 80 |\n',encoding='utf-8')
csv=out/'fixture.csv';csv.write_text('Item,Value\nRevenue,120\nCost,80\n',encoding='utf-8')
results=[]
for name,fn,src in [('docx',docx.render_docx,md),('pdf',pdf.render_pdf,md),('pptx',pptx.render_pptx,md),('xlsx',xlsx.render_xlsx,csv)]:
 try:
  dest=out/f'test.{name}';fn(str(src),str(dest))
  if name=='pdf':valid=dest.read_bytes().startswith(b'%PDF-')
  else:
   with zipfile.ZipFile(dest) as z:valid=z.testzip() is None
  if name=='docx':
   from docx import Document
   valid=valid and any('Origo Test Report' in p.text for p in Document(dest).paragraphs)
  if name=='pptx':
   from pptx import Presentation
   valid=valid and len(Presentation(dest).slides)>0
  if name=='xlsx':
   from openpyxl import load_workbook
   valid=valid and load_workbook(dest).active['B2'].value==120
  results.append({'feature':name,'pass':valid,'bytes':dest.stat().st_size})
 except Exception as e:results.append({'feature':name,'pass':False,'error':f'{type(e).__name__}: {e}'})
print(json.dumps(results));(out.parent/'document-tests.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
