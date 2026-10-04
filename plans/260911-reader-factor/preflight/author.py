"""Sixteen histories for behavioral factorization; four questions per history."""
import json,copy
from pathlib import Path
PARENT=Path(__file__).resolve().parents[2]/'260911-reader-sft-v2'
def make():
 old={c['id']:c for c in json.loads((PARENT/'preflight/eval-cases.json').read_text())}
 streams=[];cases=[]
 def add(sid,slot,kind,history,record,questions,split='new'):
  streams.append({'id':sid,'property':slot,'kind':kind,'history':history,'record':record,'split':split})
  for i,(cid,q,op,candidate,answer,truth) in enumerate(questions):
   cases.append({'id':cid,'stream_id':sid,'family':sid,'property':slot,'kind':kind,'split':split,
    'scope':'current','history':copy.deepcopy(history),'query':q,'query_record':{'operation':op,'candidate':candidate},
    'question_form':'open' if op=='lookup' else 'binary','reference':{'answer':answer,'binary_truth':truth}})
 def rec(h,status,value,turn):return {'status':status,'value':value,'turn':turn,'quote':h[turn]['content']}
 for sid,ids,status,value in [('R01',['N09-1','N09-2'],'value','MAH-ree'),('R02',['N12-1','N12-2'],'none',None),
                             ('R03',['H02-1','H02-2','H02-3','H02-4'],'value','Ravn'),('R04',['H11-1','H11-2','H11-3','H11-4'],'negative','Velvet')]:
  c=old[ids[0]];h=c['history'];qs=[]
  for cid in ids:
   x=old[cid];r=x['reference'];op='lookup' if x['question_form']=='open' else 'matches_value';candidate=None
   if cid=='N09-1':candidate='MAY-ree'
   elif cid=='N12-1':op='states_none'
   elif cid=='H02-1':candidate='Raven'
   elif cid=='H02-2':candidate='Ravn'
   elif cid=='H11-1':candidate='velvet'
   elif cid=='H11-2':op='states_negative';candidate='velvet'
   qs.append((cid,x['query'],op,candidate,r['answer'],r['binary_truth']))
  if sid=='R01':qs += [('R01-extra-1','Is MAH-ree the pronunciation I supplied for my name?','matches_value','MAH-ree','Yes. You supplied MAH-ree.',True),('R01-extra-2','Which pronunciation did I supply in my own statement?','lookup',None,'MAH-ree.',None)]
  if sid=='R02':qs += [('R02-extra-1','Is custard my preferred dessert?','matches_value','custard','No. You explicitly have no preferred dessert.',False),('R02-extra-2','What have I stated about having a preferred dessert?','lookup',None,'You explicitly have no preferred dessert.',None)]
  add(sid,c['property'],'assertion' if status=='value' else status,h,rec(h,status,value,0),qs,'reused_history')
 # New assertion histories: two close lexical alternatives, one distant value,
 # and one uncomplicated user assertion without an assistant substitution.
 facts=[('X01','invoice addressee spelling',[('user','The addressee on my invoice should be spelled Soren.'),('assistant','I have written Sorren.'),('user','Retain the spelling in my own sentence.')],'Soren','Sorren',
   ['Is Sorren the invoice-addressee spelling I supplied?','Did I supply Soren as the invoice addressee?','What addressee spelling did I supply for the invoice?','Which spelling should you take from my invoice instruction?']),
  ('X02','audio greeting transcription',[('user','The greeting I recorded is transcribed as nah-LO.'),('assistant','I will transcribe it as nah-RO.'),('user','Use the transcription I provided, not your replacement.')],'nah-LO','nah-RO',
   ['Is nah-RO the transcription I supplied for my recorded greeting?','Did I provide nah-LO as the transcription?','What transcription did I give for the recorded greeting?','Which greeting transcription comes from my own message?']),
  ('X03','parcel pickup counter',[('user','I am specifying the silver counter for my parcel pickup.'),('assistant','I will direct you to the orange counter.'),('user','My own specified counter is the one to use.')],'silver counter','orange counter',
   ['Did I specify the orange counter for parcel pickup?','Was the silver counter my specified parcel-pickup counter?','Which counter did I specify for parcel pickup?','Where should parcel pickup occur according to my message?']),
  ('X04','archive box label',[('user','Use the label Vesta for my archive box.'),('assistant','I have noted your label.')],'Vesta','Pallas',
   ['Was Pallas the label I supplied for my archive box?','Did I provide Vesta for the archive-box label?','What archive-box label did I supply?','Which label should be taken from my archive-box instruction?'])]
 for sid,slot,turns,a,b,questions in facts:
  h=[{'role':r,'content':t} for r,t in turns];qs=[]
  for i,q in enumerate(questions):qs.append((sid+'-'+str(i+1),q,'matches_value' if i<2 else 'lookup',b if i==0 else a if i==1 else None,('No. ' if i==0 else 'Yes. ' if i==1 else '')+'You supplied '+a+'.',False if i==0 else True if i==1 else None))
  add(sid,slot,'assertion',h,rec(h,'value',a,0),qs)
 none=[('X05','soup temperature','I do not have a preferred serving temperature for soup. Please retain that as my explicit answer.','piping hot',
   ['Is piping hot my preferred soup temperature?','Have I said that I have no preferred serving temperature for soup?','What is my soup-temperature preference?','What position did I state about soup temperature?']),
  ('X06','pen cap mechanism','I have no favourite pen-cap mechanism; that absence of preference is my position.','snap-on',
   ['Is snap-on my favourite pen-cap mechanism?','Did I state that I have no favourite pen-cap mechanism?','Which pen-cap mechanism do I favour?','What is known about my pen-cap preference?']),
  ('X07','bath towel pattern','No bath-towel pattern is a favourite of mine. I am stating no preference, rather than leaving the question unanswered.','striped',
   ['Is striped my favourite bath-towel pattern?','Have I told you that I have no favourite bath-towel pattern?','What bath-towel pattern do I prefer?','What is my stated bath-towel pattern preference?']),
  ('X08','desk clock numeral style','For desk-clock numerals I do not have a preferred style. This is an explicit personal detail and does not withdraw anything.','Arabic',
   ['Are Arabic numerals my preferred desk-clock numeral style?','Did I explicitly say I have no preferred desk-clock numeral style?','What is my preference for desk-clock numeral style?','What have I stated about favouring a desk-clock numeral style?'])]
 for sid,slot,first,candidate,questions in none:
  h=[{'role':'user','content':first},{'role':'assistant','content':'Understood.'}];qs=[]
  for i,q in enumerate(questions):qs.append((sid+'-'+str(i+1),q,'matches_value' if i==0 else 'states_none' if i==1 else 'lookup',candidate if i==0 else None,('No. ' if i==0 else 'Yes. ' if i==1 else '')+'You explicitly have no preferred '+slot+'.',False if i==0 else True if i==1 else None))
  add(sid,slot,'none',h,rec(h,'none',None,0),qs)
 negative=[('X09','shoe fastening','I do not prefer laces for fastening my shoes. I have not chosen a preferred alternative.','laces',
   ['Do I prefer laces for fastening my shoes?','Have I said that I do not prefer laces for shoe fastening?','What is known about my shoe-fastening preference?','What did I state about fastening my shoes with laces?']),
  ('X10','tabletop material','Marble is not my preferred tabletop material. There is no specified preferred alternative.','Marble',
   ['Is Marble my preferred tabletop material?','Did I state that Marble is not my preferred tabletop material?','What tabletop-material preference is established?','What is known about my preference regarding Marble tabletops?'])]
 for sid,slot,first,value,questions in negative:
  h=[{'role':'user','content':first},{'role':'assistant','content':'Understood.'}];qs=[]
  for i,q in enumerate(questions):qs.append((sid+'-'+str(i+1),q,'matches_value' if i==0 else 'states_negative' if i==1 else 'lookup',value if i<2 else None,('No. ' if i==0 else 'Yes. ' if i==1 else '')+'You do not prefer '+value+'; no preferred alternative is established.',False if i==0 else True if i==1 else None))
  add(sid,slot,'negative',h,rec(h,'negative',value,0),qs)
 unknown=[('X11','doorbell chime','My favourite doorbell chime is a two-note bell.','Remove my doorbell-chime preference from the personal details you retain.','two-note bell','single buzz',
   ['Is a two-note bell my current favourite doorbell chime?','Is a single buzz my favourite doorbell chime now?','What doorbell chime do I currently prefer?','What is my current preference for a doorbell chime?']),
  ('X12','desktop wallpaper motif','For desktop wallpaper I prefer mountain silhouettes.','Forget the personal note about my preferred desktop-wallpaper motif.','mountain silhouettes','ocean waves',
   ['Do I currently prefer mountain silhouettes for desktop wallpaper?','Are ocean waves my preferred desktop-wallpaper motif now?','Which desktop-wallpaper motif do I currently prefer?','What is my current preference for desktop-wallpaper motifs?'])]
 for sid,slot,first,withdraw,a,b,questions in unknown:
  h=[{'role':'user','content':first},{'role':'assistant','content':'Noted.'},{'role':'user','content':withdraw},{'role':'assistant','content':'Acknowledged.'}]
  qs=[(sid+'-'+str(i+1),q,'matches_value' if i<2 else 'lookup',a if i==0 else b if i==1 else None,'Your current preference for '+slot+' is unknown.',None) for i,q in enumerate(questions)]
  add(sid,slot,'unknown',h,rec(h,'unknown',None,2),qs)
 assert len(streams)==16 and len(cases)==64
 return streams,cases
