"""64 new source-grounded questions, 16 independently worded histories."""
import copy

def make_test_cases():
    cases=[]
    def add(fam,slot,kind,turns,qs):
        h=[{'role':r,'content':s} for r,s in turns]
        for j,row in enumerate(qs):
            q,a,truth,mode,value,polarity,support,scope,forbidden=row
            cases.append({'id':fam+'-'+str(j+1),'family':fam,'property':slot,'kind':kind,'split':'test',
                'scope':scope,'question_form':'open' if truth is None and j in (2,3) else 'binary',
                'history':copy.deepcopy(h),'query':q,'reference':{'answer':a,'binary_truth':truth,'mode':mode,
                'current_value':value,'polarity':polarity,'evidence_turns':support,'forbidden_old_values':forbidden}})
    def known(q,a,t,v):return(q,a,t,'known',v,'positive',[0],'current',[])
    add('H01','workshop access code','assertion_conflict',[
        ('user','The access code I am giving you for the workshop is L8R.'),
        ('assistant','I copied that as LBR.'),('user','Please rely on the code I typed; the version you copied is wrong.')],[
        known('Was LBR the workshop access code that I gave you?','No. You gave L8R.',False,'L8R'),
        known('Did I give L8R for access to the workshop?','Yes. You gave L8R.',True,'L8R'),
        known('What code did I type for workshop access?','L8R.',None,'L8R'),
        known('Which workshop code should you take from my message?','L8R.',None,'L8R')])
    add('H02','reservation surname spelling','assertion_conflict',[
        ('user','Put the reservation under the surname Ravn. That is the spelling I am providing.'),
        ('assistant','I have it under Raven.'),('user','Keep the exact spelling from my request.')],[
        known('Is Raven the surname spelling that I supplied for the reservation?','No. You supplied Ravn.',False,'Ravn'),
        known('Did my reservation request use the spelling Ravn?','Yes. It used Ravn.',True,'Ravn'),
        known('How did I spell the surname for the reservation?','Ravn.',None,'Ravn'),
        known('What surname spelling should be taken from my request?','Ravn.',None,'Ravn')])
    add('H03','equipment serial suffix','assertion_conflict',[
        ('user','For the equipment log, the serial suffix I am reporting is 6032.'),
        ('assistant','The suffix has been entered as 6302.'),('user','Your entry transposes the digits; my report is the source to use.')],[
        known('Was 6302 the serial suffix I reported?','No. You reported 6032.',False,'6032'),
        known('Is 6032 the equipment serial suffix from my report?','Yes. You reported 6032.',True,'6032'),
        known('Which serial suffix did I report for the equipment?','6032.',None,'6032'),
        known('What equipment suffix should replace the transposed entry?','6032.',None,'6032')])
    add('H04','gallery delivery entrance','assertion_conflict',[
        ('user','The delivery entrance I am specifying for the gallery is the east archway.'),
        ('assistant','I will direct the delivery to the west archway.'),('user','Use the entrance I specified in my message.')],[
        known('Did I specify the west archway for the gallery delivery?','No. You specified the east archway.',False,'east archway'),
        known('Was the east archway the gallery delivery entrance I specified?','Yes. You specified the east archway.',True,'east archway'),
        known('Which entrance did I specify for the gallery delivery?','The east archway.',None,'east archway'),
        known('Where should the gallery delivery go according to my instruction?','The east archway.',None,'east archway')])
    # None is a known state. All four phrasings assert it without a withdrawal.
    none_rows=[('H05','envelope size','I do not have a favourite envelope size. That is my answer, and I want you to retain it.','C6',
        ['Is C6 my favourite envelope size?','Have I told you that I lack a favourite envelope size?','What is my envelope-size preference?','What did I say about having a favourite envelope size?']),
      ('H06','curtain fabric','As far as curtain fabric goes, none is a favourite of mine. I am explicitly telling you I have no preference.','linen',
        ['Is linen my favourite curtain fabric?','Did I explicitly state that I have no favourite curtain fabric?','What curtain-fabric preference have I expressed?','What is known about my favourite curtain fabric?']),
      ('H07','breakfast bowl shape','There is no breakfast-bowl shape that I favour over the others. Please remember that I have no favourite shape.','oval',
        ['Is oval my favourite breakfast-bowl shape?','Have I said that I have no favourite breakfast-bowl shape?','Which breakfast-bowl shape do I favour?','What is my stated position on breakfast-bowl shape?']),
      ('H08','wall-clock frame finish','I do not have a preferred finish for a wall-clock frame. I mean that I have no preference; I am not asking you to erase an earlier choice.','brushed steel',
        ['Is brushed steel my preferred wall-clock frame finish?','Did I say I have no preferred wall-clock frame finish?','What is my preference for the finish of a wall-clock frame?','What preference position did I state about wall-clock frames?'])]
    for fam,slot,text,candidate,qs in none_rows:
        answer=f'You have explicitly stated that you have no preferred {slot}.'
        add(fam,slot,'explicit_none',[('user',text),('assistant','I understand your stated position.')],
            [(q,('No. ' if j==0 else 'Yes. ' if j==1 else '')+answer,False if j==0 else True if j==1 else None,'known',None,'none',[0],'current',[]) for j,q in enumerate(qs)])
    negative_rows=[('H09','notebook binding','Spiral binding is not what I prefer for notebooks. I am making a negative statement without choosing another binding.','spiral binding',
        ['Do I prefer spiral binding for notebooks?','Have I said that spiral binding is not my notebook preference?','What have I stated about spiral notebook binding?','What notebook-binding preference is established?']),
      ('H10','navigation voice accent','I do not prefer the Australian accent for navigation voice prompts. I have left the alternative unspecified.','Australian accent',
        ['Is the Australian accent my preferred navigation voice accent?','Did I explicitly say I do not prefer the Australian accent for navigation?','What is known about my navigation voice-accent preference?','What did I say about the Australian navigation voice accent?']),
      ('H11','chair upholstery','Velvet is not my preferred upholstery for a chair. I have not selected a preferred material.','velvet',
        ['Do I prefer velvet upholstery for a chair?','Have I stated that velvet is not my preferred chair upholstery?','What have I told you about velvet chair upholstery?','What is known about my chair-upholstery preference?']),
      ('H12','document page numbering','I do not prefer Roman numerals for document page numbers; no alternative scheme has been chosen.','Roman numerals',
        ['Are Roman numerals my preferred document page numbering?','Have I explicitly said that I do not prefer Roman-numeral page numbers?','What is my stated position on Roman-numeral page numbering?','What is established about my document page-numbering preference?'])]
    for fam,slot,text,value,qs in negative_rows:
        answer=f'You do not prefer {value} for {slot}; no preferred alternative is established.'
        add(fam,slot,'explicit_negative',[('user',text),('assistant','Understood.')],
            [(q,('No. ' if j==0 else 'Yes. ' if j==1 else '')+answer,False if j==0 else True if j==1 else None,'known',value,'negative',[0],'current',[]) for j,q in enumerate(qs)])
    unknown_rows=[('H13','bedside lamp shade','For a bedside lamp I most like a pleated shade.','Delete the personal detail about my favourite bedside-lamp shade.','pleated','smooth',
        ['Is pleated my favourite bedside-lamp shade now?','Is smooth my current favourite bedside-lamp shade?','What bedside-lamp shade do I currently favour?','Which shade did my first message favour before I asked for deletion?']),
      ('H14','calendar week start','I prefer my calendar week to begin on Monday.','Remove the preference about the starting day of my calendar week.','Monday','Sunday',
        ['Do I currently prefer a Monday start for my calendar week?','Do I currently prefer a Sunday start for my calendar week?','Which starting day do I currently prefer for the calendar week?','What starting day did my initial message prefer, before removal?']),
      ('H15','photo album cover','The cover I like best for a photo album is linen.','Erase my personal choice for photo-album covers.','linen','suede',
        ['Is linen the photo-album cover I like best now?','Is suede my current favourite photo-album cover?','What cover do I currently favour for photo albums?','What cover did my original message favour before erasure?']),
      ('H16','garden watering time','For watering my garden I prefer dawn.','Do not keep the preference about when I water my garden.','dawn','dusk',
        ['Is dawn my current preferred garden-watering time?','Is dusk my current preferred garden-watering time?','When do I currently prefer to water my garden?','What watering time did my first message prefer before withdrawal?'])]
    for fam,slot,first,withdraw,a,b,qs in unknown_rows:
        rows=[(q,f'Your current preference for {slot} is unknown.',None,'unknown',None,None,[2],'current',[a]) for q in qs[:3]]
        rows.append((qs[3],'Your first message said: '+first,None,'historical',None,None,[0,2],'historical',[a]))
        add(fam,slot,'withdrawal_scope',[('user',first),('assistant','Noted.'),('user',withdraw),('assistant','The request is acknowledged.')],rows)
    assert len(cases)==64
    return cases
