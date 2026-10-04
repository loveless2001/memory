"""Twenty-four separately worded held-out source families, two questions each."""
import copy


def make_test_cases():
    cases=[]
    def add(slot,kind,turns,questions,mode,value,polarity,truth,support,forbidden=(),scope='current'):
        family=f'E{len(cases)//2+1:02d}'
        history=[{'role':r,'content':s} for r,s in turns]
        for i,(query,answer) in enumerate(questions):
            cases.append({'id':family+('-binary' if i==0 else '-open'),'family':family,'kind':kind,
                'property':slot,'split':'test','question_form':'binary' if i==0 else 'open','scope':scope,
                'history':copy.deepcopy(history),'query':query,
                'reference':{'answer':answer,'mode':mode,'current_value':value,'polarity':polarity,
                    'binary_truth':truth if i==0 else None,'evidence_turns':support,'forbidden_old_values':list(forbidden)}})

    add('calendar view','baseline',[
        ('user','When I open my calendar, the view I like best is the agenda view.'),
        ('assistant','Thanks for explaining how you use it.')],[
        ('Is the agenda view the calendar view I like best?','Yes. You prefer the agenda view.'),
        ('Which calendar view do I like best?','The agenda view.')],
        'known','agenda view','positive',True,[0])
    add('diagram orientation','baseline',[
        ('user','For diagrams in my own reports, landscape is my preferred orientation.'),
        ('assistant','I can help lay out a diagram that way.')],[
        ('Do I prefer portrait orientation for my report diagrams?','No. You prefer landscape orientation.'),
        ('What orientation do I prefer for diagrams in my reports?','Landscape.')],
        'known','landscape','positive',False,[0])
    add('alarm tone','withdrawal',[
        ('user','The alarm sound I prefer is woodblock.'),('assistant','Noted.'),
        ('user','Erase the personal note about which alarm sound I prefer.'),('assistant','I understand the request.')],[
        ('Is woodblock the alarm sound I currently prefer?','Your current alarm-tone preference is unknown.'),
        ('What alarm sound do I currently prefer?','Your current alarm-tone preference is unknown.')],
        'unknown',None,None,None,[2],['woodblock'])
    add('citation style','assistant_echo',[
        ('user','In my documents I favour author-date citations.'),('assistant','Author-date citations, understood.'),
        ('user','Take my citation-style preference out of the personal information you use.'),
        ('assistant','I removed the note saying you favour author-date citations.'),
        ('assistant','For your next paper, I remember that you favour author-date citations.')],[
        ('Do I currently favour author-date citations?','Your current citation-style preference is unknown.'),
        ('Which citation style do I currently favour?','Your current citation-style preference is unknown.')],
        'unknown',None,None,None,[2],['author-date'])
    add('meeting lighting','same',[
        ('user','I like warm white lighting best for meetings.'),('assistant','I have recorded that.'),
        ('user','Please erase my preference about meeting lighting.'),('assistant','Acknowledged.'),
        ('user','I am supplying the information anew: warm white is the meeting lighting I like best.')],[
        ('Is warm white the lighting I currently like best for meetings?','Yes. You prefer warm white lighting for meetings.'),
        ('What meeting lighting do I currently like best?','Warm white lighting.')],
        'known','warm white','positive',True,[4])
    add('museum visit day','different',[
        ('user','My favourite day to visit a museum is Wednesday.'),('assistant','Thanks.'),
        ('user','Discard my museum-day preference.'),('assistant','Understood.'),
        ('user','The preference to use from now on is Saturday for museum visits.')],[
        ('Is Wednesday my favourite day for museum visits now?','No. Your current preferred museum day is Saturday.'),
        ('Which day do I currently favour for museum visits?','Saturday.')],
        'known','Saturday','positive',False,[4],['Wednesday'])
    add('lunch grain','different_without_withdrawal',[
        ('user','I choose barley over other grains for my lunch.'),('assistant','Understood.'),
        ('user','That lunch choice has changed: I now prefer quinoa instead.')],[
        ('Do I prefer barley for lunch now?','No. You now prefer quinoa.'),
        ('What grain do I now prefer for lunch?','Quinoa.')],
        'known','quinoa','positive',False,[2])
    add('notebook ruling','same',[
        ('user','Dot grid is the notebook ruling I prefer.'),('assistant','Recorded.'),
        ('user','Delete my notebook-ruling preference from your personal notes.'),
        ('assistant','The note was deleted.'),
        ('user','You may use this as my new current statement: I prefer dot grid notebooks.')],[
        ('Do I currently prefer dot grid notebooks?','Yes. You currently prefer dot grid notebooks.'),
        ('Which notebook ruling do I prefer at present?','Dot grid.')],
        'known','dot grid','positive',True,[4])
    add('search-result density','ownership',[
        ('user','For a novel, I wrote this line for fictional Oren: "I like compact search results best." Please check the dialogue.'),
        ('assistant','The speaker in that dialogue is Oren.')],[
        ('Do I like compact search results best?','Your search-result density preference is unknown.'),
        ('What search-result density do I personally like best?','Your search-result density preference is unknown.')],
        'unknown',None,None,None,[0])
    add('hand-soap scent','ownership',[
        ('user','My neighbour Dara sent me this: "My favourite hand-soap scent is verbena." Help me write a friendly response to Dara.'),
        ('assistant','You could thank Dara for the recommendation.')],[
        ('Is verbena my favourite hand-soap scent?','Your hand-soap scent preference is unknown.'),
        ('Which hand-soap scent is my favourite?','Your hand-soap scent preference is unknown.')],
        'unknown',None,None,None,[0])
    add('calendar highlight color','quote_after_withdrawal',[
        ('user','Navy is my favourite color for calendar highlights.'),('assistant','Noted.'),
        ('user','Stop retaining my calendar-highlight color preference.'),('assistant','Understood.'),
        ('user','A fictional scheduler named Tavi says, "Navy is my favourite color for calendar highlights." Does Tavi\'s line read naturally?')],[
        ('Is navy my current favourite calendar-highlight color?','Your current calendar-highlight color preference is unknown.'),
        ('What color do I currently favour for calendar highlights?','Your current calendar-highlight color preference is unknown.')],
        'unknown',None,None,None,[2],['navy','Navy'])
    add('hiking pace','quote_after_withdrawal',[
        ('user','For hikes, the pace I prefer is leisurely.'),('assistant','Got it.'),
        ('user','Remove the detail about my hiking pace preference.'),('assistant','Done.'),
        ('user','My cousin Jo says, "For hikes, the pace I prefer is leisurely." I want to reply to Jo\'s message.'),
        ('assistant','That describes Jo\'s preference.')],[
        ('Do I currently prefer a leisurely hiking pace?','Your current hiking-pace preference is unknown.'),
        ('What hiking pace do I currently prefer?','Your current hiking-pace preference is unknown.')],
        'unknown',None,None,None,[2],['leisurely'])
    add('name-badge placement','other_then_user',[
        ('user','A script has fictional Beck say, "I prefer my name badge on the right." Can you copy-edit it?'),
        ('assistant','That is Beck\'s line.'),
        ('user','As for my own badge, I prefer it on the left.')],[
        ('Do I prefer my own name badge on the right?','No. You prefer it on the left.'),
        ('Where do I prefer to place my own name badge?','On the left.')],
        'known','left','positive',False,[2])
    add('lunch-break duration','other_then_user',[
        ('user','My teammate Ren wrote, "I prefer a forty-minute lunch break." Please polish Ren\'s wording.'),
        ('assistant','I can help with Ren\'s sentence.'),
        ('user','Separately, my personal preference is a thirty-minute lunch break.')],[
        ('Is a forty-minute lunch break my preference?','No. You prefer a thirty-minute lunch break.'),
        ('How long do I prefer my lunch break to be?','Thirty minutes.')],
        'known','thirty-minute','positive',False,[2])
    add('diagram line pattern','unrelated_withdrawal',[
        ('user','For my diagrams I favour dashed lines; for presentation backgrounds I favour ivory.'),
        ('assistant','I noted both preferences.'),
        ('user','Erase only the presentation-background preference. Preserve the line-pattern preference.')],[
        ('Do I currently favour dashed lines for my diagrams?','Yes. You still favour dashed lines.'),
        ('Which line pattern do I favour for my diagrams?','Dashed lines.')],
        'known','dashed','positive',True,[0])
    add('indentation width','unrelated_withdrawal',[
        ('user','My indentation preference is two spaces. My break location is the courtyard.'),
        ('assistant','Understood.'),
        ('user','Forget where I take breaks; leave my indentation preference alone.')],[
        ('Is two spaces still my indentation preference?','Yes. Your indentation preference is two spaces.'),
        ('What indentation width do I prefer?','Two spaces.')],
        'known','two spaces','positive',True,[0])
    add('bottle material','negative',[
        ('user','I do not prefer glass for my water bottle. I am not specifying a favourite alternative material.'),
        ('assistant','Thanks for making that distinction.')],[
        ('Do I prefer a glass water bottle?','No. You explicitly do not prefer glass.'),
        ('What is known about my bottle-material preference?','You do not prefer glass; your preferred alternative material is unknown.')],
        'known','glass','negative',False,[0])
    add('commute transport','negative',[
        ('user','Ferries are not my preferred way to commute. This is a current negative preference, not an instruction to erase a note.'),
        ('assistant','Understood.')],[
        ('Are ferries my preferred way to commute?','No. You explicitly said ferries are not your preferred way to commute.'),
        ('What can you say about my preference regarding ferries for commuting?','You do not prefer ferries for commuting; no preferred alternative is established.')],
        'known','ferries','negative',False,[0])
    add('window covering','no_preference',[
        ('user','Between possible window coverings, I have no favourite at all. Please treat that lack of preference as my stated position.'),
        ('assistant','I understand.')],[
        ('Are blinds my favourite window covering?','No. You explicitly have no favourite window covering.'),
        ('What is my window-covering preference?','You explicitly have no favourite window covering.')],
        'known',None,'none',False,[0])
    add('report-header font','no_preference',[
        ('user','I have no preferred font for report headers. I am telling you that I have no preference, rather than withholding an answer.'),
        ('assistant','Understood.')],[
        ('Is Atkinson my preferred report-header font?','No. You explicitly have no preferred report-header font.'),
        ('Which font preference have I stated for report headers?','You explicitly stated that you have no preferred report-header font.')],
        'known',None,'none',False,[0])
    add('lecture seating','historical',[
        ('user','At lectures, I favour a seat in the front row.'),('assistant','Noted.'),
        ('user','Delete my lecture-seating preference.'),('assistant','The request is acknowledged.')],[
        ('Did my first message say I favoured the front row at lectures, before the deletion request?','Yes. Your first message said you favoured a seat in the front row at lectures.'),
        ('What seating did my first message favour at lectures, before I withdrew the preference?','Your first message said you favoured a seat in the front row at lectures.')],
        'historical',None,None,True,[0,2],['front row'],scope='historical')
    add('mobile keyboard layout','historical',[
        ('user','For my mobile keyboard, I prefer Colemak.'),('assistant','Understood.'),
        ('user','Erase that keyboard-layout preference.'),('assistant','Acknowledged.'),
        ('user','My new current preference is QWERTY for the mobile keyboard.')],[
        ('Did my original first message prefer Colemak for the mobile keyboard?','Yes. Your original first message preferred Colemak for the mobile keyboard.'),
        ('Which mobile keyboard layout did my original first message prefer?','Your original first message preferred Colemak.')],
        'historical','QWERTY','positive',True,[0],['Colemak'],scope='historical')
    add('playback speed','assistant_conflict',[
        ('user','My preferred playback speed for recorded talks is 1.0x.'),
        ('assistant','I will assume that your preferred playback speed is 1.25x.'),
        ('user','Use the speed that I stated, not the different speed in your reply.')],[
        ('Is 1.25x my preferred playback speed for recorded talks?','No. You stated a preference for 1.0x.'),
        ('What playback speed should you use according to my stated preference?','1.0x.')],
        'known','1.0x','positive',False,[0])
    add('summary language','multiple_updates',[
        ('user','The language I prefer for summaries is Italian.'),('assistant','Noted.'),
        ('user','Forget my summary-language preference.'),
        ('user','My new preference is Dutch for summaries.'),('assistant','Understood.'),
        ('user','Withdraw that language preference as well.'),
        ('user','Now retain this as my current preference: summaries in Catalan.')],[
        ('Is Dutch my current preferred language for summaries?','No. Your current preference is Catalan.'),
        ('Which language do I currently prefer for summaries?','Catalan.')],
        'known','Catalan','positive',False,[6],['Italian','Dutch'])
    assert len(cases)==48
    return cases
