"""Source-grounded synthetic supervision; no regression/test cases or outputs."""
import copy

FAMILIES = [
    ('terminal color scheme','Solarized','Dracula'),
    ('puzzle magazine','Logic Monthly','Riddle Review'),
    ('desk plant','aloe','fern'),
    ('camera strap','woven cotton','neoprene'),
    ('travel cushion','inflatable','memory foam'),
    ('tea container','ceramic tin','glass jar'),
    ('bookmark material','cork','leather'),
    ('cycling glove color','maroon','olive'),
    ('weather display','hourly chart','daily icons'),
    ('email greeting','Hello','Good morning'),
    ('luggage tag shape','round','hexagonal'),
    ('workshop snack','rice crackers','dried apricots'),
    ('photo border','thin black','wide white'),
    ('study timer length','twenty minutes','thirty-five minutes'),
    ('garden path surface','brick','gravel'),
    ('video subtitle size','medium','large'),
]
KINDS=('baseline','withdrawal','different','same','ownership','quote_after_withdrawal',
       'other_then_user','unrelated_withdrawal','assistant_echo','negative','no_preference','historical')


def msg(role,text): return {'role':role,'content':text}


def statement(slot,value,style):
    return [f'My preferred {slot} is {value}.',
            f'For {slot}, I prefer {value}.',
            f'My personal preference for {slot} is {value}.',
            f'I prefer {value} for my {slot}.'][style]


def make_training_cases():
    cases=[]
    for fi,(slot,old,new) in enumerate(FAMILIES):
        family=f'T{fi+1:02d}'
        for ki,kind in enumerate(KINDS):
            style=(fi+ki)%4;first=statement(slot,old,style)
            history=[msg('user',first),msg('assistant','Understood.')]
            mode='known';value=old;polarity='positive';support=[0];scope='current';forbidden=[]
            withdrawal=[f'Please forget my preference for {slot}.',
                        f'Remove the personal detail about my preferred {slot}.',
                        f'Do not retain my {slot} preference for future answers.',
                        f'I withdraw the personal preference I gave you for {slot}.'][style]
            if kind in ('withdrawal','different','same','quote_after_withdrawal','assistant_echo','historical'):
                history += [msg('user',withdrawal),msg('assistant','I acknowledge your request.')]
                mode='unknown';value=None;polarity=None;support=[2];forbidden=[old]
            if kind in ('different','same'):
                value=new if kind=='different' else old
                history += [msg('user','Here is my current preference: '+statement(slot,value,(style+1)%4)),msg('assistant','Noted.')]
                mode='known';polarity='positive';support=[4]
                if kind=='same':forbidden=[]
            if kind=='ownership':
                history=[msg('user',f'Please edit a line from the fictional character Neri: "{first}"'),
                         msg('assistant','This line belongs to fictional Neri.')]
                mode='unknown';value=None;polarity=None;support=[]
            if kind=='quote_after_withdrawal':
                history += [msg('user',f'My colleague Ivo wrote, "{first}" Please improve Ivo\'s wording.'),
                            msg('assistant','That is Ivo\'s statement.')]
            if kind=='other_then_user':
                history=[msg('user',f'Fictional Neri says, "{first}" Please proofread that line.'),
                         msg('assistant','The speaker is Neri.'),
                         msg('user','For me personally: '+statement(slot,new,(style+1)%4)),msg('assistant','Understood.')]
                value=new;support=[2]
            if kind=='unrelated_withdrawal':
                history += [msg('user','I also prefer the north room for meetings.'),msg('assistant','Noted.'),
                            msg('user',f'Forget only my meeting-room preference. Keep my {slot} preference.'),
                            msg('assistant','I acknowledge the limited withdrawal.')]
            if kind=='assistant_echo':
                history[3]=msg('assistant',f'I have removed your old preference for {old}.')
                history += [msg('assistant',f'As a reminder, your preferred {slot} is {old}.')]
            if kind=='negative':
                history=[msg('user',f'I do not prefer {old} for my {slot}. I have not named a preferred alternative.'),
                         msg('assistant','Understood.')]
                mode='known';value=old;polarity='negative';support=[0]
            if kind=='no_preference':
                history=[msg('user',f'I explicitly have no preferred {slot}. This is my current personal position.'),
                         msg('assistant','Understood.')]
                mode='known';value=None;polarity='none';support=[0]
            if kind=='historical':scope='historical';mode='historical';support=[0,2]
            for form in ('binary','open'):
                query=(f'Is {old} my current preferred {slot}?' if form=='binary'
                       else f'What is currently known about my preference for {slot}?')
                if scope=='historical':
                    query=(f'Did my first message say I preferred {old} for {slot}, before I withdrew it?' if form=='binary'
                           else f'What did my first message say about my {slot} preference, before I withdrew it?')
                    target=('Yes. ' if form=='binary' else '')+'Your first message said: '+first
                    truth=True
                elif mode=='unknown':target=f'Your current preference for {slot} is unknown.';truth=None
                elif polarity=='none':
                    target=('No. ' if form=='binary' else '')+f'You have explicitly stated that you have no preferred {slot}.';truth=False
                elif polarity=='negative':
                    target=('No. ' if form=='binary' else '')+f'You explicitly do not prefer {old} for your {slot}; a preferred alternative is unknown.';truth=False
                else:
                    truth=value==old
                    target=(('Yes. ' if truth else 'No. ') if form=='binary' else '')+f'Your current preferred {slot} is {value}.'
                cases.append({'id':f'{family}-{kind}-{form}','family':family,'kind':kind,'property':slot,
                    'split':'train','question_form':form,'scope':scope,'statement_style':style,
                    'history':copy.deepcopy(history),'query':query,
                    'reference':{'answer':target,'mode':mode,'current_value':value,'polarity':polarity,
                                 'binary_truth':truth if form=='binary' else None,'evidence_turns':support,
                                 'forbidden_old_values':forbidden}})
    assert len(cases)==384
    return cases
