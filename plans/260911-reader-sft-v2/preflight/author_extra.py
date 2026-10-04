"""128 new references authored from source, not from evaluation outputs."""
import copy
FACTS=[('locker identifier','B-14','B-41'),('project label','Orchid','Granite'),
       ('receipt code','PV6','VP6'),('screen name','Maple','Juniper'),
       ('parking bay','C7','C9'),('collection time','08:20','08:50'),
       ('device hostname','birch01','birch10'),('sample label','Q2A','Q2B')]
PREFERENCES=[('presentation transition','fade','cut'),('map distance unit','kilometres','miles'),
 ('keyboard backlight color','amber','cyan'),('shopping bag material','canvas','jute'),
 ('stitch pattern','herringbone','zigzag'),('spreadsheet grid color','gray','blue'),
 ('watch display','analogue','digital'),('podcast episode format','interview','solo')]
def msg(role,text):return {'role':role,'content':text}
def make_extra():
    cases=[]
    def add(cid,family,kind,slot,h,q,a,truth,value,polarity,mode,support,form,forbidden=()):
        cases.append({'id':cid,'family':family,'kind':kind,'property':slot,'split':'train','scope':'current',
            'question_form':form,'history':copy.deepcopy(h),'query':q,'reference':{'answer':a,'mode':mode,
            'current_value':value,'polarity':polarity,'binary_truth':truth,'evidence_turns':support,
            'forbidden_old_values':list(forbidden)}})
    for i,(slot,a,b) in enumerate(FACTS):
        fam=f'A{i+1:02d}'
        for conflict in (False,True):
            h=[msg('user',f'My {slot} is {a}.'),msg('assistant',f'I will use {b} as your {slot}.' if conflict else 'I have noted the value you supplied.')]
            if conflict:h += [msg('user','Use the value in my own statement, rather than the different one in your reply.')]
            questions=[(f'Is {a} the {slot} I supplied?',f'Yes. You supplied {a}.',True),
                (f'Is {b} the {slot} I supplied?',f'No. You supplied {a}.',False),
                (f'Which {slot} did I supply?',f'You supplied {a}.',None),
                (f'Did I give {b} as my {slot}?',f'No. You gave {a}.',False)]
            for j,(q,answer,truth) in enumerate(questions):
                add(f'{fam}-{int(conflict)}-{j}',fam,'assertion_conflict' if conflict else 'assertion_match',slot,h,q,answer,truth,a,'positive','known',[0],'open' if truth is None else 'binary')
    for i,(slot,a,b) in enumerate(PREFERENCES):
        fam=f'P{i+1:02d}'
        for kind in ('positive','none','negative','withdrawn'):
            first=f'I prefer {a} for my {slot}.';value=a;polarity='positive';mode='known';support=[0];forbidden=[]
            if kind=='none':
                first=[f'I do not have a preferred {slot}. This is an explicit personal fact.',
                       f'I have no favourite {slot}; that is my stated position.',
                       f'No {slot} is my favourite. I am explicitly stating that I have no preference.',
                       f'Regarding {slot}, my answer is that I have no preference. This is not missing information.'][i%4]
                value=None;polarity='none'
            if kind=='negative':first=f'I do not prefer {a} for my {slot}. I have not specified a preferred alternative.';polarity='negative'
            h=[msg('user',first),msg('assistant','Understood.')]
            if kind=='withdrawn':
                h += [msg('user',f'Forget my personal preference about {slot}.'),msg('assistant','Acknowledged.')]
                value=None;polarity=None;mode='unknown';support=[2];forbidden=[a]
            for form in ('binary','open'):
                q=f'Is {a} my preferred {slot}?' if form=='binary' else f'What is my {slot} preference?'
                truth=None
                if kind=='positive':truth=True;answer=('Yes. ' if form=='binary' else '')+f'Your preferred {slot} is {a}.'
                elif kind=='none':truth=False;answer=('No. ' if form=='binary' else '')+f'You explicitly have no preferred {slot}.'
                elif kind=='negative':truth=False;answer=('No. ' if form=='binary' else '')+f'You do not prefer {a}; your preferred alternative is unknown.'
                else:answer=f'Your current preference for {slot} is unknown.'
                add(f'{fam}-{kind}-{form}',fam,'contrast_'+kind,slot,h,q,answer,truth if form=='binary' else None,value,polarity,mode,support,form,forbidden)
    assert len(cases)==128
    return cases
