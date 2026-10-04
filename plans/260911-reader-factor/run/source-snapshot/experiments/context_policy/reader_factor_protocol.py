"""Explicit evidence records and restricted oracle-query projection."""
import json
EXTRACT_SYSTEM='''Identify the final supported USER fact about TARGET PROPERTY in the archive.
Output only JSON after the supplied ANSWER prefix, with exactly these keys:
{"status":"value|none|negative|unknown","value":null,"turn":0,"quote":"exact user text"}.
Use status value for a supplied positive fact, none only for an explicit statement
of having no preference, negative for an explicitly non-preferred value, and
unknown when the current detail has been withdrawn or is not established.
For value/negative, value is the minimal verbatim value string from the USER
source; for none/unknown it is null. turn and quote must identify the USER
statement supporting this state; quote is an exact substring with sufficient
context. For a withdrawal cite the withdrawal. If there is no supporting user
statement use turn null and quote null. An assistant substitution or another
speaker's quotation cannot establish a user fact. Later USER statements control;
withdrawal establishes unknown, not a negative or no-preference state. Do not
answer any downstream question. No explanations or markdown fences.'''
SELECT_SYSTEM='''Answer CURRENT QUESTION in at most 90 words using only EVIDENCE RECORD.
Continue the supplied ANSWER prefix with plain answer text, no action markers.
The record's value status gives the user's own supplied fact. Status none means
an explicit statement of having no preference; it is known, not missing data.
Status negative denies preference for the named value, with no alternative
established. Status unknown establishes neither a candidate nor its opposite.
Answer the precise requested question; distinguish a candidate in a question
from the actual supplied value. A correct value cannot justify the wrong Yes/No.
If QUERY INTERPRETATION is supplied, it states the operation and candidate for
the question: matches_value compares that candidate to the user fact;
states_none asks whether the user explicitly stated no preference;
states_negative asks whether the user stated a negative about its candidate;
lookup asks for the supported fact/preference, including known none or negative.
Do not add unsupported claims or restate withdrawn assignments.'''

def extraction_messages(history,slot):
    return [{'role':'system','content':EXTRACT_SYSTEM},{'role':'user','content':'TARGET PROPERTY\n'+slot+'\nARCHIVE\n'+json.dumps([{'turn':i,**m} for i,m in enumerate(history)],ensure_ascii=False)}]
def semantic(record):return {'status':record['status'],'value':record['value']}
def parse_record(text,history):
    try:
        r=json.loads(text)
        if type(r) is not dict or set(r)!={'status','value','turn','quote'}:raise ValueError('exact four-key record required')
        if r['status'] not in ('value','none','negative','unknown'):raise ValueError('unknown status')
        if r['status'] in ('value','negative'):
            if not isinstance(r['value'],str) or not r['value'].strip():raise ValueError('value string required')
        elif r['value'] is not None:raise ValueError('none/unknown value must be null')
        if r['turn'] is None:
            if r['quote'] is not None or r['status']!='unknown':raise ValueError('absent evidence allowed only for unknown')
        else:
            if type(r['turn']) is not int or not 0<=r['turn']<len(history):raise ValueError('invalid evidence turn')
            m=history[r['turn']]
            if m['role']!='user' or not isinstance(r['quote'],str) or not r['quote'] or r['quote'] not in m['content']:raise ValueError('invalid user quote')
            if r['status'] in ('value','negative') and r['value'] not in r['quote']:raise ValueError('value absent from quote')
        return {'valid':True,'record':r,'error':None}
    except (ValueError,TypeError) as e:
        return {'valid':False,'record':{'status':'unknown','value':None,'turn':None,'quote':None},'error':str(e)}
def record_messages(slot,record,question,query=None):
    # Serialization is canonical, so saved artifact key order cannot affect prompts.
    content='EVIDENCE RECORD\n'+json.dumps({'property':slot,**record},sort_keys=True,ensure_ascii=False)
    if query is not None:content+='\nQUERY INTERPRETATION\n'+json.dumps(query,sort_keys=True,ensure_ascii=False)
    return [{'role':'system','content':SELECT_SYSTEM},{'role':'user','content':content+'\nCURRENT QUESTION\n'+question}]
def project(record,query):
    """Case-folded literal-string diagnostic, with externally supplied question interpretation."""
    s,v=record['status'],record['value'];op=query['operation'];candidate=query.get('candidate')
    equal=isinstance(candidate,str) and isinstance(v,str) and candidate.casefold()==v.casefold()
    if op=='lookup':return {'kind':s,'value':v}
    if op=='matches_value':
        if s=='value':return {'kind':'boolean','value':equal}
        if s=='none' or s=='negative' and equal:return {'kind':'boolean','value':False}
        return {'kind':'unknown','value':None}
    if op=='states_none':return {'kind':'boolean','value':s=='none'}
    if op=='states_negative':return {'kind':'boolean','value':s=='negative' and equal}
    raise ValueError('unsupported query operation')
