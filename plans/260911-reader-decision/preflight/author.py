"""Matched source-authored decisions/prose targets, with separate novel test wording."""
import copy,json
TRAIN=[
 ('badge emblem','heron','otter','fact'),
 ('workbench mat texture','ribbed','smooth','preference'),
 ('weeknight hobby','bookbinding','whittling','enjoyment'),
 ('ceramic cup glaze','celadon','cobalt','preference'),
 ('courier reference','KN-42','NK-42','fact'),
 ('hiking sock length','ankle','crew','preference'),
 ('indoor recreation','juggling','calligraphy','enjoyment'),
 ('bedspread weave','waffle','twill','preference'),
 ('studio room code','M-8','M-9','fact'),
 ('lantern fuel','lamp oil','kerosene','preference'),
 ('quiet-day activity','mosaic making','stamp collecting','enjoyment'),
 ('watering can spout','long neck','short neck','preference'),
 ('equipment alias','Rilenn','Rilen','fact'),
 ('picture mount color','ivory','charcoal','preference'),
 ('holiday craft','basket weaving','soap carving','enjoyment'),
 ('travel pouch closure','zipper','drawstring','preference')]
KINDS=('positive','negative','none','withdrawal','same','different','ownership','historical')
TEST=[
 ('museum ticket surname','Kova','Kovva','fact'),
 ('radio call sign','Tarin','Taryn','fact'),
 ('parcel sorting zone','violet bay','amber bay','fact'),
 ('newsletter typeface','Garamond','Futura','preference'),
 ('after-dinner activity','model building','card tricks','enjoyment'),
 ('curtain tieback material','satin','rope','preference'),
 ('bicycle saddle padding','gel','foam','preference'),
 ('weekend pastime','geocaching','fishing','enjoyment'),
 ('soap fragrance','lavender','cedar','preference'),
 ('table napkin fold','fan fold','pocket fold','preference'),
 ('shower curtain pattern','polka dots','chevrons','preference'),
 ('bread crust color','dark brown','pale gold','preference'),
 ('ceramic bowl depth','shallow','deep','preference'),
 ('reading lamp bulb shape','globe','candle','preference'),
 ('backpack pocket layout','side pockets','front pocket','preference'),
 ('appointment reminder sound','woodblock','marimba','preference'),
 ('file cabinet handle','bar pull','ring pull','preference'),
 ('morning leisure activity','bird photography','crochet','enjoyment'),
 ('suitcase wheel count','four wheels','two wheels','preference'),
 ('ferry booking code','DP-31','DP-13','fact'),
 ('lunchbox divider material','bamboo','silicone','preference'),
 ('trail marker symbol','crescent','diamond','fact'),
 ('pencil grip shape','triangular','round','preference'),
 ('weekday relaxation','watercolor painting','knitting','enjoyment'),
 ('bread basket lining','cotton','linen cloth','preference'),
 ('document storage tag','Arlen','Arllen','fact'),
 ('handbag strap width','wide','narrow','preference'),
 ('table runner length','short','long','preference'),
 ('autumn hobby','wood turning','leather stamping','enjoyment'),
 ('wristwatch strap fastener','buckle','clasp','preference'),
 ('drawer liner scent','lemon','mint','preference'),
 ('account nickname','Nerin','Nerim','fact'),
 ('park activity','disc golf','roller skating','enjoyment'),
 ('window blind slat width','broad','slim','preference'),
 ('bathrobe collar style','shawl collar','hooded collar','preference'),
 ('event badge code','UR-8','RU-8','fact'),
 ('tea-tray rim shape','oval rim','square rim','preference'),
 ('winter indoor activity','origami folding','puzzle solving','enjoyment'),
 ('camera bag compartment','padded insert','mesh insert','preference'),
 ('kitchen timer alarm','triple beep','single chime','preference')]

def msg(role,text):return {'role':role,'content':text}
def positive(slot,v,rel,fresh,style):
 if rel=='fact':return f'The {slot} I am providing is {v}.' if fresh else f'My supplied {slot} is {v}.'
 if rel=='enjoyment':return f'As my {slot}, I enjoy {v}.' if fresh else f'I enjoy {v} for my {slot}.'
 return [f'For {slot}, {v} is what I favour.',f'My favourite {slot} is {v}.'][style%2] if fresh else f'I prefer {v} for my {slot}.'
def negative(slot,v,rel,fresh):
 if rel=='fact':return f'{v} is not the {slot} I supplied. I have left the correct value unspecified.'
 if rel=='enjoyment':return f'I do not enjoy {v} as my {slot}. I have not named an activity I enjoy instead.'
 return (f'{v} is not my preferred {slot}. No favourite alternative has been selected.' if fresh else
         f'I do not prefer {v} for my {slot}. I have not named a preferred alternative.')
def none(slot,fresh,style):
 if fresh:return [f'No {slot} is a favourite of mine. This is my stated position.',
                  f'For {slot}, my answer is that I have no preference.',
                  f'I do not have a favourite {slot}; this is an explicit fact rather than a missing answer.',
                  f'I favour no particular {slot}. Please keep that no-preference position.',
                  f'I explicitly have no preferred {slot}. I am not withdrawing a prior choice.'][style%5]
 return [f'I explicitly have no preferred {slot}.',f'I do not have a favourite {slot}; that is my answer.',
         f'Regarding {slot}, I have no preference. Please retain that fact.',f'No {slot} is my favourite. This is not an unanswered question.'][style%4]

def binary_question(slot,candidate,relation,fresh,style=0,scope='current'):
 if scope=='historical':return (f'Did the first user passage give {candidate} for {slot}, before the removal?' if fresh else f'Did my first statement give {candidate} for {slot}, before I withdrew it?')
 if relation=='fact':return (f'Was {candidate} the {slot} that I supplied?' if style%2==0 else f'Did I specify {candidate} for {slot}?') if fresh else f'Is {candidate} the {slot} I supplied?'
 if relation=='enjoyment':return f'Do I currently enjoy {candidate} as my {slot}?' if fresh else f'Do I enjoy {candidate} for my {slot} now?'
 return (f'Is {candidate} my favourite {slot} at present?' if style%2==0 else f'Do I currently favour {candidate} for {slot}?') if fresh else f'Is {candidate} my current preferred {slot}?'

def rows_for(family,slot,a,b,relation,kind,fresh,index):
 # No question is used to construct the source history; one history has four forms.
 rel='preference' if kind=='none' else relation
 first=positive(slot,a,rel,fresh,index);h=[msg('user',first),msg('assistant','Noted.')]
 status='value';value=a;turn=0;scope='current'
 withdrawal=(f'Erase the personal detail about my {slot}; it should no longer be used as my current information.' if fresh else f'Please forget my personal detail about {slot}.')
 if kind=='positive':
  h[1]=msg('assistant',f'I will record {b} for your {slot}.')
  h.append(msg('user','Keep what I actually said, including its exact wording.' if fresh else 'Use my own statement, not your substitution.'))
 if kind=='negative':h=[msg('user',negative(slot,a,rel,fresh)),msg('assistant','Understood.')];status='negative'
 if kind=='none':h=[msg('user',none(slot,fresh,index)),msg('assistant','Understood.')];status='none';value=None
 if kind in ('withdrawal','same','different','historical'):
  h += [msg('user',withdrawal),msg('assistant','Acknowledged.')];status='unknown';value=None;turn=2
 if kind=='withdrawal' and index%2==0:
  h += [msg('user',f'A fictional character called Oren says, "{first}" Please edit Oren\'s line.'),msg('assistant','This is Oren\'s line.')]
 if kind in ('same','different'):
  value=a if kind=='same' else b
  h += [msg('user',('Here is the detail I now want you to use: ' if fresh else 'I am re-establishing this current detail: ')+positive(slot,value,rel,fresh,index+1)),msg('assistant','Noted.')]
  status='value';turn=4
 if kind=='ownership':
  h=[msg('user',f'Proofread this first-person line spoken by fictional Oren: "{first}" It belongs to the character.'),msg('assistant','The speaker is Oren, not you.')]
  status='unknown';value=None;turn=0
 if kind=='historical':status='value';value=a;turn=0;scope='historical'
 quote=h[turn]['content']
 if scope=='historical':
  questions=[(binary_question(slot,a,rel,fresh,index,scope),'match',a,'supported'),
             (binary_question(slot,b,rel,fresh,index+1,scope),'match',b,'contradicted'),
             (f'What did the first user passage state about {slot}, before the removal?' if fresh else f'What did my first statement say about {slot}, before withdrawal?','lookup',None,'answer'),
             (f'Quote my original statement concerning {slot}.' if fresh else f'What was my original statement about {slot}?','lookup',None,'answer')]
 elif kind=='negative':
  nq=(f'Have I stated that {a} is not my preferred {slot}?' if rel=='preference' else
      f'Did I say that I do not enjoy {a} for my {slot}?' if rel=='enjoyment' else
      f'Did I state that {a} is not the {slot} I supplied?')
  questions=[(binary_question(slot,a,rel,fresh,index),'match',a,'contradicted'),(nq,'states_negative',a,'supported')]
 elif kind=='none':
  nq=f'Have I explicitly said that I have no favourite {slot}?' if fresh else f'Did I state that I have no preference for {slot}?'
  questions=[(binary_question(slot,a,rel,fresh,index),'match',a,'contradicted'),(nq,'states_none',None,'supported')]
 elif status=='unknown':questions=[(binary_question(slot,a,rel,fresh,index),'match',a,'unknown'),(binary_question(slot,b,rel,fresh,index+1),'match',b,'unknown')]
 else:
  candidates=[b,a] if kind=='positive' else [a,b]
  questions=[(binary_question(slot,v,rel,fresh,index+j),'match',v,'supported' if v==value else 'unknown' if rel=='enjoyment' else 'contradicted') for j,v in enumerate(candidates)]
 if scope!='historical':
  qs=([f'What {slot} have I specified?',f'Which value should you take from my statement about {slot}?'] if rel=='fact' else
      [f'What do I enjoy as my {slot}?',f'What is known about my enjoyment of {slot}?'] if rel=='enjoyment' else
      [f'What is my preference for {slot}?',f'What position have I stated about {slot}?']) if fresh else (
      [f'What {slot} did I supply?',f'What is currently known about my {slot}?'] if rel=='fact' else
      [f'What have I said I enjoy for my {slot}?',f'What is my current position on enjoying {slot}?'] if rel=='enjoyment' else
      [f'Which {slot} do I prefer?',f'What is known about my {slot} preference?'])
  questions += [(q,'lookup',None,'unknown' if status=='unknown' else 'answer') for q in qs]
 if scope=='current' and rel in ('preference','enjoyment'):
  current_open=([f'What is my current preference for {slot}?',f'What position is currently established about my {slot}?'] if rel=='preference' else
                [f'What do I currently enjoy as my {slot}?',f'What is currently known about my enjoyment of {slot}?'])
  for j in (2,3):questions[j]=(current_open[j-2],'lookup',None,'unknown' if status=='unknown' else 'answer')
 # A negative about A leaves B unknown; explicit none would instead deny a favourite B.
 if kind=='negative':
  questions[2]=(binary_question(slot,b,rel,fresh,index+1),'match',b,'unknown')
 # Keep present-state questions explicitly current when a fact was withdrawn/replaced.
 if rel=='fact' and kind in ('withdrawal','same','different','ownership'):
  questions=[((f'Is {candidate} my current {slot}?' if fresh else f'Is {candidate} the current value for my {slot}?') if op=='match' else
              (f'What is my current {slot}?' if j==2 else f'Which value is established for my {slot} now?'),op,candidate,decision)
             for j,(_,op,candidate,decision) in enumerate(questions)]
 result=[]
 for j,(query,op,candidate,decision) in enumerate(questions):
  gold={'scope':scope,'relation':rel,'status':status,'value':value,'operation':op,'candidate':candidate,'decision':decision,'turn':turn,'quote':quote}
  # Ordinary targets independently describe the source state, not generated JSON.
  prefix={'supported':'Yes. ','contradicted':'No. ','unknown':'','answer':''}[decision]
  if scope=='historical':answer=prefix+'Your first statement said: '+first
  elif status=='unknown':answer=f'Your current detail about {slot} is unknown.'
  elif decision=='unknown':
   answer=('Whether you enjoy the queried activity is unknown. You '+('do not enjoy' if status=='negative' else 'enjoy')+f' {value}.' if rel=='enjoyment' else
           f'Whether you prefer {candidate} for your {slot} is unknown. You do not prefer {value}.' if rel=='preference' else
           f'Whether {candidate} is your supplied {slot} is unknown. You stated that {value} is not the supplied value.')
  elif status=='none':answer=prefix+f'You explicitly have no preferred {slot}.'
  elif status=='negative':
   answer=prefix+(f'You do not enjoy {value} for your {slot}; no alternative activity you enjoy is established.' if rel=='enjoyment' else
                  f'You do not prefer {value} for your {slot}; no preferred alternative is established.' if rel=='preference' else
                  f'You stated that {value} is not your supplied {slot}; the correct value is unknown.')
  else:answer=prefix+(f'You enjoy {value} for your {slot}.' if rel=='enjoyment' else f'Your preferred {slot} is {value}.' if rel=='preference' else f'You supplied {value} for {slot}.')
  result.append({'id':f'{family}-{kind}-{j+1}' if not fresh else f'{family}-{j+1}','family':family,'stream_id':family+'-'+kind,'property':slot,'kind':kind,
   'split':'test' if fresh else 'train','scope':scope,'question_form':'open' if op=='lookup' else 'binary','history':copy.deepcopy(h),'query':query,
   'reference':{'answer':answer,'mode':'historical' if scope=='historical' else 'unknown' if status=='unknown' else 'known','current_value':None if scope=='historical' else value,
    'polarity':None if status=='unknown' else {'value':'positive','negative':'negative','none':'none'}[status],
    'binary_truth':True if decision=='supported' else False if decision=='contradicted' else None,'evidence_turns':[turn],
    'forbidden_old_values':[a] if kind in ('withdrawal','different') else [],'decision':gold}})
 return result

def make_training():
 rows=[]
 for i,(slot,a,b,rel) in enumerate(TRAIN):
  for kind in KINDS:rows+=rows_for(f'TR{i+1:02d}',slot,a,b,rel,kind,False,i)
 assert len(rows)==512
 return rows

def make_test():
 rows=[]
 for i,(slot,a,b,rel) in enumerate(TEST):rows+=rows_for(f'J{i+1:02d}',slot,a,b,rel,KINDS[i//5],True,i)
 assert len(rows)==160
 return rows
