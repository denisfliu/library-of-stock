#!/usr/bin/env python3
"""Generate remaining analysis JSONs for the batch."""
import json, os

def write_json(slug, data):
    path = f"output/{slug}_analysis.json"
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Wrote {path}")

# ============ SAUL BELLOW ============
write_json("saul_bellow", {
  "topic": "Saul Bellow",
  "summary": "Canadian-American Jewish Nobel Prize-winning author, associated with Chicago. Known for intellectual, philosophically dense novels about Jewish-American life. His dying words were reportedly 'Was I a man or was I a jerk?'",
  "works": [
    {"name": "The Adventures of Augie March", "indicator": "Novel",
     "description": "A picaresque novel whose title character is described as 'an American, Chicago born.' Augie works for the crippled businessman Einhorn, catches eagles with Thea Fenchel, survives a shipwreck by escaping on a lifeboat with a madman, and in Mexico discovers his friend Sylvester has become a bodyguard for Trotsky. The novel's famous opening has Augie claiming he will be 'first to knock on the door, first admitted.'",
     "clues": [
       {"clue": "Title character is 'an American, Chicago born'; picaresque novel", "frequency": 8, "tendency": "giveaway", "examples": ["whose title character is described as 'an American, Chicago born'", "The Adventures of Augie March is part of this genre"]},
       {"clue": "Augie works for Einhorn; catches eagles with Thea Fenchel", "frequency": 3, "tendency": "mid", "examples": ["The protagonist works for Einhorn and falls in love with Thea Fenchel"]},
       {"clue": "Sylvester becomes bodyguard for Trotsky in Mexico", "frequency": 1, "tendency": "power", "examples": ["his friend Sylvester has become a bodyguard for Trotsky"]},
       {"clue": "Opening: 'first to knock on the door, first admitted'", "frequency": 1, "tendency": "power", "examples": ["Augie claims he will be 'first to [knock on the door], first admitted'"]}
     ]},
    {"name": "Seize the Day", "indicator": "Novel",
     "description": "A novella about the failed actor Tommy Wilhelm, who speculates on lard commodities on the advice of the sinister psychologist Dr. Tamkin and loses everything. His withholding father Dr. Adler refuses to give him money. The novel ends with Tommy weeping uncontrollably at a stranger's funeral. Tommy worked as an extra whose fake bagpipes made no sound.",
     "clues": [
       {"clue": "Tommy Wilhelm conned by Dr. Tamkin into investing in lard; father Dr. Adler refuses help", "frequency": 8, "tendency": "giveaway", "examples": ["a character who is conned into a scheme to invest in lard by Dr. Tamkin", "Dr. Adler refuses to give his son Tommy Wilhelm any money"]},
       {"clue": "Tommy weeps uncontrollably at a stranger's funeral at the end", "frequency": 4, "tendency": "mid", "examples": ["burst into uncontrollable tears during the funeral of a stranger", "weeping uncontrollably at a stranger's funeral after losing all his money"]},
       {"clue": "Tommy worked as an extra with fake bagpipes that made no sound", "frequency": 1, "tendency": "power", "examples": ["works as an extra playing a musician but is embarrassed when no sound comes out of his fake bagpipes"]}
     ]},
    {"name": "Herzog", "indicator": "Novel",
     "description": "A novel about a divorced Jewish professor who writes unsent letters to various celebrities while mulling over his divorce from Madeleine and his betrayal by his friend Valentine Gerbasch. The title character writes the book Romanticism and Christianity. He is arrested for concealing his father's revolver in a car while visiting his daughter. The scholar Shapiro admits 'my Russian is not what it could be.'",
     "clues": [
       {"clue": "Divorced professor writes unsent letters to celebrities; betrayed by Valentine Gerbasch", "frequency": 5, "tendency": "giveaway", "examples": ["mulls over his divorce from Madeleine and his betrayal by Valentine Gerbasch, while writing letters he never sends", "a divorced Jewish professor in Herzog"]},
       {"clue": "Arrested for concealing father's revolver; writes Romanticism and Christianity", "frequency": 2, "tendency": "mid", "examples": ["The title character of a novel by this author is arrested for concealing his father's revolver in a car"]},
       {"clue": "Scholar Shapiro admits 'my Russian is not what it could be'", "frequency": 1, "tendency": "power", "examples": ["the scholar Shapiro admits 'my Russian is not what it could be'"]}
     ]},
    {"name": "Henderson the Rain King", "indicator": "Novel",
     "description": "An American millionaire travels to Africa, tries to rid the Arnewi of frogs in their cistern, and accidentally earns the title 'Rain King' from the Wariri tribe by lifting a statue of the goddess Mummah. King Dahfu hunts a lion he believes is the reincarnation of his dead father. Henderson's guide Romilayu leads him between villages. The novel was likely inspired by Melville Herskovits's The Cattle Complex in East Africa.",
     "clues": [
       {"clue": "American millionaire in Africa; lifts statue of Mummah; becomes Rain King of the Wariri", "frequency": 7, "tendency": "giveaway", "examples": ["the title millionaire travels to Africa and lifts a statue of Mummah to earn the titular epithet", "tries to get rid of the frogs in the cistern of the Arnewi"]},
       {"clue": "King Dahfu hunts a lion (reincarnation of his dead father)", "frequency": 2, "tendency": "mid", "examples": ["King Dahfu is on a quest to hunt the lion that he believes is that reincarnation of his dead father"]},
       {"clue": "Guide Romilayu leads Henderson between villages", "frequency": 2, "tendency": "power", "examples": ["this guide who leads a title character to the village of the Arnewi"]},
       {"clue": "Inspired by Herskovits's The Cattle Complex in East Africa", "frequency": 1, "tendency": "power", "examples": ["likely inspired by Melville Herskovits' book The Cattle Complex in East Africa"]}
     ]},
    {"name": "Humboldt's Gift", "indicator": "Novel",
     "description": "Based on Bellow's real-life friendship with Delmore Schwartz, who is fictionalized as the writer Von Humboldt Fleisher. Bellow fictionalized himself as the writer Charlie Citrine. Gaddis's JR beat this novel for the National Book Award.",
     "clues": [
       {"clue": "Charlie Citrine befriends Von Humboldt Fleisher (based on Delmore Schwartz)", "frequency": 8, "tendency": "giveaway", "examples": ["fictionalized himself as Charlie Citrine in a novel based on his real-life friendship with Delmore Schwartz", "Schwartz was the basis for Von Humboldt Fleischer"]},
       {"clue": "Gaddis's JR beat Humboldt's Gift for the National Book Award", "frequency": 1, "tendency": "power", "examples": ["Gaddis's book JR beat out this other writer's novel Humboldt's Gift to win the National Book Award"]}
     ]},
    {"name": "Ravelstein", "indicator": "Novel",
     "description": "Bellow's final novel, a fictionalization of his friend Allan Bloom (author of The Closing of the American Mind). The title professor Abe is dying of AIDS at the Hotel Crillon. Bellow's fourth wife, the mathematician Alexandra Tulcea, is fictionalized as Vela. The Malaysian character Nikki is Ravelstein's lover. Bellow nearly died of ciguatera poisoning from a fish, which inspired part of the novel.",
     "clues": [
       {"clue": "Fictionalization of Allan Bloom; title character dying of AIDS at Hotel Crillon", "frequency": 6, "tendency": "giveaway", "examples": ["fictionalized Allan Bloom in his final novel, Ravelstein", "a political philosopher who studied under Alexandre Kojeve and is diagnosed with AIDS"]},
       {"clue": "Bellow ate a fish with ciguatera toxin; wife Tulcea fictionalized as Vela", "frequency": 2, "tendency": "power", "examples": ["this author nearly died after eating a fish full of ciguatera toxin", "this author's fourth wife, the mathematician Alexandra Tulcea, is lightly fictionalized as Vela"]}
     ]},
    {"name": "General / Biographical", "indicator": "Author",
     "description": "Bellow is identified as a Canadian-American Jewish author, Nobel laureate. His dying words were 'Was I a man or was I a jerk?' His friendship with Martin Amis and Christopher Hitchens is well-documented. He infamously asked 'Who is the Tolstoy of the Zulus?' and defended himself by citing Mofolo's Chaka and his teacher Melville Herskovits. He translated Isaac Bashevis Singer's 'Gimpel the Fool' from Yiddish. He coined the term 'Good Intentions Paving Company.' He wrote Mr. Sammler's Planet (about a Holocaust survivor), The Dean's December, More Die of Heartbreak, and novellas The Actual and A Theft.",
     "clues": [
       {"clue": "Canadian-American Jewish author; Nobel laureate", "frequency": 5, "tendency": "giveaway", "examples": ["this Canadian-American author", "this Nobel winner"]},
       {"clue": "Dying words: 'Was I a man or was I a jerk?'", "frequency": 2, "tendency": "power", "examples": ["his dying words, 'Was I a man or was I a jerk?'"]},
       {"clue": "'Who is the Tolstoy of the Zulus?' controversy; cited Mofolo's Chaka and Herskovits", "frequency": 3, "tendency": "mid", "examples": ["infamously asked, 'Who is the Tolstoy of the Zulus?'"]},
       {"clue": "Translated Singer's 'Gimpel the Fool' from Yiddish", "frequency": 1, "tendency": "power", "examples": ["This American author's translation of 'Gimpel the Fool' introduced Isaac Bashevis Singer's Yiddish stories"]},
       {"clue": "Mr. Sammler's Planet about a Holocaust survivor", "frequency": 2, "tendency": "mid", "examples": ["wrote about a Holocaust survivor in Mr. Sammler's Planet"]}
     ]}
  ],
  "comprehensive_summary": "Saul Bellow is a Canadian-American Jewish Nobel laureate, consistently associated with Chicago and intellectual Jewish-American fiction. His dying words were reportedly 'Was I a man or was I a jerk?' He is fictionalized in Martin Amis's Inside Story.\n\nThe Adventures of Augie March is his most identified novel, a picaresque about 'an American, Chicago born' who works for Einhorn, catches eagles with Thea Fenchel, and discovers his friend guarding Trotsky in Mexico. Seize the Day follows the failed actor Tommy Wilhelm, conned by Dr. Tamkin into lard speculation, refused money by his father Dr. Adler, and ending in uncontrollable weeping at a stranger's funeral. Herzog depicts a divorced professor writing unsent letters while processing betrayal by Valentine Gerbasch.\n\nHenderson the Rain King follows an American millionaire who earns the title from the Wariri tribe by lifting the statue of Mummah, guided by Romilayu through the Arnewi and Wariri villages. Humboldt's Gift fictionalizes Bellow's friendship with Delmore Schwartz as Von Humboldt Fleisher, with Bellow as Charlie Citrine. Ravelstein is his final novel, fictionalizing Allan Bloom (of The Closing of the American Mind) as a professor dying of AIDS at the Hotel Crillon.\n\nBellow's controversy over asking 'Who is the Tolstoy of the Zulus?' is frequently clued, as is his defense citing Thomas Mofolo's Chaka and his teacher Melville Herskovits. He translated Singer's 'Gimpel the Fool' and wrote about a Holocaust survivor in Mr. Sammler's Planet.",
  "recursive_suggestions": [],
  "links": [
    {"text": "Saul Bellow — Wikipedia", "url": "https://en.wikipedia.org/wiki/Saul_Bellow"},
    {"text": "The Adventures of Augie March — Wikipedia", "url": "https://en.wikipedia.org/wiki/The_Adventures_of_Augie_March"},
    {"text": "Seize the Day — Wikipedia", "url": "https://en.wikipedia.org/wiki/Seize_the_Day_(novel)"},
    {"text": "Herzog — Wikipedia", "url": "https://en.wikipedia.org/wiki/Herzog_(novel)"},
    {"text": "Henderson the Rain King — Wikipedia", "url": "https://en.wikipedia.org/wiki/Henderson_the_Rain_King"}
  ],
  "category": "Literature", "subcategory": "American Literature",
  "year": 1915, "continent": "North America", "country": "United States",
  "tags": ["Jewish-American literature"],
  "cards": [
    {"type": "basic", "indicator": "Novel", "front": "Novel: picaresque about 'an American, Chicago born' who works for Einhorn and catches eagles with Thea Fenchel", "back": "The Adventures of Augie March (Saul Bellow)", "work": "The Adventures of Augie March", "frequency": 8, "tags": []},
    {"type": "basic", "indicator": "Novel", "front": "Novel: the failed actor Tommy Wilhelm is conned into investing in lard by Dr. Tamkin; his father Dr. Adler refuses to help; ends weeping at a stranger's funeral", "back": "Seize the Day (Saul Bellow)", "work": "Seize the Day", "frequency": 8, "tags": []},
    {"type": "basic", "indicator": "Novel", "front": "Novel: a divorced professor writes unsent letters to celebrities while processing betrayal by Valentine Gerbasch and divorce from Madeleine", "back": "Herzog (Saul Bellow)", "work": "Herzog", "frequency": 5, "tags": []},
    {"type": "basic", "indicator": "Novel", "front": "Novel: an American millionaire lifts the statue of Mummah to become Rain King of the Wariri; King Dahfu hunts a lion believed to be his reincarnated father", "back": "Henderson the Rain King (Saul Bellow)", "work": "Henderson the Rain King", "frequency": 7, "tags": []},
    {"type": "basic", "indicator": "Novel", "front": "Novel: Charlie Citrine's friendship with Von Humboldt Fleisher, a character based on Delmore Schwartz", "back": "Humboldt's Gift (Saul Bellow)", "work": "Humboldt's Gift", "frequency": 8, "tags": []},
    {"type": "basic", "indicator": "Novel", "front": "Novel: fictionalizes Allan Bloom as a professor dying of AIDS at the Hotel Crillon; inspired in part by the author nearly dying of ciguatera poisoning", "back": "Ravelstein (Saul Bellow)", "work": "Ravelstein", "frequency": 6, "tags": []},
    {"type": "basic", "indicator": "Author", "front": "Author: infamously asked 'Who is the Tolstoy of the Zulus?'; defended himself by citing Thomas Mofolo's Chaka and his teacher Melville Herskovits", "back": "Saul Bellow", "work": "General / Biographical", "frequency": 3, "tags": []},
    {"type": "basic", "indicator": "Author", "front": "Author: translated Isaac Bashevis Singer's 'Gimpel the Fool' from Yiddish into English", "back": "Saul Bellow", "work": "General / Biographical", "frequency": 1, "tags": []}
  ],
  "cross_refs": []
})

# ============ JAMES BALDWIN ============
write_json("james_baldwin", {
  "topic": "James Baldwin",
  "summary": "African-American author, essayist, and civil rights intellectual who spent much of his adult life in France. Known for essays on race, identity, and sexuality, and for novels exploring African-American religious and social life.",
  "works": [
    {"name": "Go Tell It on the Mountain", "indicator": "Novel", "description": "Baldwin's autobiographical first novel, set on the 14th birthday of the preacher's son John Grimes. The third section, 'The Threshing-Floor,' depicts John's spiritual rebirth at the Temple of the Fire Baptized Church. Gabriel is revealed not to be John's true father. Gabriel abandoned his illegitimate son Royal. The second part consists of three prayers.", "clues": [
      {"clue": "Set on John Grimes's 14th birthday; spiritual rebirth at the Temple of the Fire Baptized", "frequency": 10, "tendency": "giveaway", "examples": ["set on the 14th birthday of a preacher's son named John Grimes", "'The Threshing-Floor' section depicts John's spiritual rebirth"]},
      {"clue": "Gabriel not John's true father; abandoned illegitimate son Royal", "frequency": 3, "tendency": "mid", "examples": ["Gabriel is revealed not to be the true father of the protagonist", "one character abandons his illegitimate son Royal"]},
      {"clue": "Baldwin's preacher father inspired the novel", "frequency": 2, "tendency": "mid", "examples": ["this man's preacher father, who partially inspired his novel Go Tell it on the Mountain"]}
    ]},
    {"name": "Notes of a Native Son", "indicator": "Work", "description": "Baldwin's 1955 essay collection, partly titled after Richard Wright's Native Son. Contains 'Everybody's Protest Novel' (criticizing Uncle Tom's Cabin and linking Wright's Bigger Thomas to Stowe), 'Many Thousands Gone,' and the title essay about his father's death coinciding with the Detroit race riots. In 'Notes of a Native Son,' Baldwin describes throwing a water jug at a waitress who refused to serve him. The collection critiques Carmen Jones for its 'sterile and distressing eroticism' and its casting of darker-skinned actors in lower-class roles.", "clues": [
      {"clue": "Contains 'Everybody's Protest Novel' attacking Uncle Tom's Cabin and linking Wright to Stowe", "frequency": 6, "tendency": "mid", "examples": ["linked him to a 'timeless battle' with Harriet Beecher Stowe", "'Everybody's Protest Novel' argues that Wright's novel is 'trapped by the American image of Negro life'"]},
      {"clue": "Title essay: father's death, Detroit race riots, throwing a water jug at a waitress", "frequency": 3, "tendency": "mid", "examples": ["Baldwin describes throwing a water jug at a waitress who refused to serve him", "father's death coincides with the Detroit race riots"]},
      {"clue": "Critiques Carmen Jones for casting and racial subtext", "frequency": 3, "tendency": "power", "examples": ["criticizes the 'sterile and distressing eroticism' of Otto Preminger's film Carmen Jones"]}
    ]},
    {"name": "The Fire Next Time", "indicator": "Work", "description": "Baldwin's influential essay collection containing 'My Dungeon Shook' (a letter to his nephew on the 100th anniversary of the Emancipation Proclamation) and 'Down at the Cross' (about his dinner with Elijah Muhammad). The title comes from the Negro spiritual 'Mary Don't You Weep.' The structure inspired Ta-Nehisi Coates's Between the World and Me. Jesmyn Ward's anthology The Fire This Time references this work.", "clues": [
      {"clue": "Letter to nephew; dinner with Elijah Muhammad; title from 'Mary Don't You Weep'", "frequency": 8, "tendency": "giveaway", "examples": ["a letter to his nephew about race to mark one hundred years of emancipation", "Baldwin's dinner with Elijah Muhammed"]},
      {"clue": "Inspired structure of Coates's Between the World and Me", "frequency": 2, "tendency": "mid", "examples": ["The structure of Between the World and Me by Ta-Nehisi Coates was inspired by a book by this author"]},
      {"clue": "Jesmyn Ward's The Fire This Time references this title", "frequency": 1, "tendency": "power", "examples": ["Ward edited an anthology of essays and poems called The Fire This Time, a nod to this other author's The Fire Next Time"]}
    ]},
    {"name": "Giovanni's Room", "indicator": "Novel", "description": "Set in Paris, the narrator David recounts his affair with the Italian bartender Giovanni on the eve of Giovanni's execution for murdering the bar owner Guillaume. David struggles with his homosexuality despite his engagement to his fiancee Hella. David's intimacy is associated with feelings of being 'dirty.' The novel was groundbreaking for depicting a same-sex relationship.", "clues": [
      {"clue": "David's affair with Giovanni in Paris; Giovanni guillotined for murdering Guillaume; fiancee Hella", "frequency": 5, "tendency": "giveaway", "examples": ["David has a disastrous gay affair with an Italian bartender in Paris", "the title character is guillotined for murdering the Parisian bar owner Guillaume"]},
      {"clue": "David associates intimacy with feeling 'dirty'; Jacques warns against this", "frequency": 1, "tendency": "power", "examples": ["David thinks of his intimacy with Joey and Giovanni in terms of this specific adjective"]}
    ]},
    {"name": "Sonny's Blues", "indicator": "Short Story", "description": "Baldwin's most famous short story, in which a math teacher narrator takes in his heroin-addicted brother Sonny after reading about his arrest in the newspaper. The story ends at a Greenwich Village jazz club where Sonny plays with Creole and his band. The narrator watches a glass of Scotch and milk shake 'like the very cup of trembling' on top of a piano, reminded of his daughter's death from polio. The story is collected in Going to Meet the Man.", "clues": [
      {"clue": "Math teacher takes in heroin-addicted jazz-playing brother; ends in Greenwich Village jazz club", "frequency": 6, "tendency": "mid", "examples": ["an unnamed math teacher takes in his heroin-addicted brother and watches him play jazz at a nightclub", "the title heroin-addicted character plays a song with Creole and his band in a Greenwich village jazz club"]},
      {"clue": "Glass of Scotch and milk shakes 'like the very cup of trembling'; daughter's death from polio", "frequency": 2, "tendency": "power", "examples": ["a glass of Scotch and milk shake 'like the very cup of trembling' on top of a piano"]},
      {"clue": "Collected in Going to Meet the Man", "frequency": 2, "tendency": "mid", "examples": ["included in the collection Going to Meet the Man"]}
    ]},
    {"name": "The Devil Finds Work", "indicator": "Work", "description": "Baldwin's book-length essay on film criticism. He analyzes the racial subtext of The Exorcist, describes the same 'loyal maid archetype' from Birth of a Nation to Guess Who's Coming to Dinner, critiques Carmen Jones for desexualizing Harry Belafonte, and compares Uncle Tom and Bigger Thomas.", "clues": [
      {"clue": "Film criticism: racial subtext of The Exorcist, Carmen Jones, loyal maid archetype", "frequency": 3, "tendency": "mid", "examples": ["analyzed the racial subtext of The Exorcist in the last chapter", "the same loyal maid archetype appears in The Birth of the Nation and Guess Who's Coming to Dinner"]}
    ]},
    {"name": "If Beale Street Could Talk", "indicator": "Novel", "description": "The sculptor Fonny is falsely accused of rape, separating him from his fiance Tish. The Rivers family struggles to free him. Adapted into a 2019 film by Barry Jenkins.", "clues": [
      {"clue": "Fonny falsely accused of rape; Tish is pregnant; adapted by Barry Jenkins", "frequency": 3, "tendency": "mid", "examples": ["the sculptor Fonny is falsely accused of rape, separating him from his fiance Tish", "adapted into a 2019 film by Barry Jenkins"]}
    ]},
    {"name": "Blues for Mister Charlie", "indicator": "Play", "description": "A 1964 play based loosely on the Emmett Till case. Richard Henry, the son of a Black minister, is killed by the white Lyle Britten, who is acquitted by a white jury. 'Mister Charlie' is African-American slang for the white man. Parnell James cannot testify against Lyle.", "clues": [
      {"clue": "Richard Henry killed by Lyle Britten; acquitted by white jury; 'Mister Charlie' = slang for white man", "frequency": 2, "tendency": "mid", "examples": ["Richard Henry, the son of a black minister, is killed by the white Lyle, who is found not guilty by a white jury"]}
    ]},
    {"name": "General / Biographical", "indicator": "Author", "description": "Baldwin spent most of his adult life in France, particularly at Saint-Paul-de-Vence. He debated William F. Buckley at Cambridge in 1965 on whether 'the American dream is at the expense of the American negro,' winning by consensus. His unfinished manuscript Remember This House (about Malcolm X, MLK, and Medgar Evers) inspired the Raoul Peck documentary I Am Not Your Negro narrated by Samuel L. Jackson. He appeared on the KQED documentary Take This Hammer. He had a complex relationship with Richard Wright, criticizing him in 'Everybody's Protest Novel' and 'Many Thousands Gone' while eulogizing him in Nobody Knows My Name. He hosted a birthday party for Black Panther leader Huey Newton. He wrote the essay 'Stranger in the Village' about being Black in Switzerland.", "clues": [
      {"clue": "Debated William F. Buckley at Cambridge 1965; won by consensus", "frequency": 4, "tendency": "mid", "examples": ["the American dream is at the expense of the American negro", "this black intellectual defeated Buckley in their Cambridge debate"]},
      {"clue": "Remember This House (unfinished) → I Am Not Your Negro (Raoul Peck, Samuel L. Jackson)", "frequency": 6, "tendency": "mid", "examples": ["unfinished manuscript Remember This House forms the basis for an oral history narrated by Samuel L. Jackson", "a 2016 documentary is based on an unfinished manuscript by this author"]},
      {"clue": "Spent adult life in France; Saint-Paul-de-Vence", "frequency": 3, "tendency": "mid", "examples": ["Most of this author's adult life was spent in France, with the later years spent at Saint-Paul-de-Vence"]},
      {"clue": "Complicated relationship with Richard Wright; criticized Native Son", "frequency": 4, "tendency": "mid", "examples": ["One of these two writers criticized the other in 'Many Thousands Gone'", "linked him to a 'timeless battle' with Harriet Beecher Stowe"]},
      {"clue": "Abandoned Malcolm X screenplay → Spike Lee's film", "frequency": 1, "tendency": "power", "examples": ["Studio interference led this author to abandon a screenplay that later became Spike Lee's film Malcolm X"]}
    ]}
  ],
  "comprehensive_summary": "James Baldwin is one of the most important African-American intellectuals and authors in quizbowl. He spent much of his adult life in France, particularly at Saint-Paul-de-Vence, and his works address race, identity, sexuality, and religion with extraordinary rhetorical power.\n\nGo Tell It on the Mountain, his autobiographical first novel, is set on the 14th birthday of preacher's son John Grimes. The third section 'The Threshing-Floor' depicts John's spiritual rebirth at the Temple of the Fire Baptized Church. Gabriel is not John's true father and had abandoned his illegitimate son Royal.\n\nBaldwin's essay collections are heavily clued. Notes of a Native Son contains 'Everybody's Protest Novel' (attacking Uncle Tom's Cabin and linking Wright's Bigger Thomas to Stowe), 'Many Thousands Gone,' and the title essay about his father's death during the Detroit race riots, including the pivotal scene of Baldwin throwing a water jug at a waitress. The Fire Next Time includes a letter to his nephew and 'Down at the Cross' (dinner with Elijah Muhammad); its structure inspired Ta-Nehisi Coates's Between the World and Me.\n\nGiovanni's Room depicts David's affair with Italian bartender Giovanni in Paris on the eve of Giovanni's execution. 'Sonny's Blues' follows a math teacher who takes in his heroin-addicted brother and watches him play jazz, ending with the 'cup of trembling' image. The Devil Finds Work is his film criticism, analyzing racial dynamics in movies from Birth of a Nation to The Exorcist.\n\nBaldwin debated William F. Buckley at Cambridge in 1965, winning by consensus. His unfinished Remember This House inspired Raoul Peck's I Am Not Your Negro. He had a complex relationship with Richard Wright and hosted a party for Huey Newton.",
  "recursive_suggestions": [],
  "links": [
    {"text": "James Baldwin — Wikipedia", "url": "https://en.wikipedia.org/wiki/James_Baldwin"},
    {"text": "Go Tell It on the Mountain — Wikipedia", "url": "https://en.wikipedia.org/wiki/Go_Tell_It_on_the_Mountain_(novel)"},
    {"text": "The Fire Next Time — Wikipedia", "url": "https://en.wikipedia.org/wiki/The_Fire_Next_Time"},
    {"text": "Giovanni's Room — Wikipedia", "url": "https://en.wikipedia.org/wiki/Giovanni%27s_Room"}
  ],
  "category": "Literature", "subcategory": "American Literature",
  "year": 1924, "continent": "North America", "country": "United States",
  "tags": ["African-American literature"],
  "cards": [
    {"type": "basic", "indicator": "Novel", "front": "Novel: set on the 14th birthday of a preacher's son; 'The Threshing-Floor' section depicts his spiritual rebirth at the Temple of the Fire Baptized", "back": "Go Tell It on the Mountain (James Baldwin)", "work": "Go Tell It on the Mountain", "frequency": 10, "tags": []},
    {"type": "basic", "indicator": "Work", "front": "Work: contains 'Everybody's Protest Novel,' which attacks Uncle Tom's Cabin and links Richard Wright's Bigger Thomas to Harriet Beecher Stowe's racial stereotypes", "back": "Notes of a Native Son (James Baldwin)", "work": "Notes of a Native Son", "frequency": 6, "tags": []},
    {"type": "basic", "indicator": "Work", "front": "Work: contains a letter to the author's nephew on the centennial of emancipation and 'Down at the Cross' about dinner with Elijah Muhammad; title from 'Mary Don't You Weep'", "back": "The Fire Next Time (James Baldwin)", "work": "The Fire Next Time", "frequency": 8, "tags": []},
    {"type": "basic", "indicator": "Novel", "front": "Novel: set in Paris; the narrator David has an affair with an Italian bartender who is guillotined for murdering the bar owner Guillaume; David's fiancee is Hella", "back": "Giovanni's Room (James Baldwin)", "work": "Giovanni's Room", "frequency": 5, "tags": []},
    {"type": "basic", "indicator": "Short Story", "front": "Short Story: a math teacher takes in his heroin-addicted brother; ends in a Greenwich Village jazz club with a glass of Scotch and milk shaking 'like the very cup of trembling'", "back": "Sonny's Blues (James Baldwin)", "work": "Sonny's Blues", "frequency": 6, "tags": []},
    {"type": "basic", "indicator": "Author", "front": "Author: debated William F. Buckley at Cambridge in 1965 on the question 'Is the American Dream at the Expense of the American Negro?' and won by consensus", "back": "James Baldwin", "work": "General / Biographical", "frequency": 4, "tags": []},
    {"type": "basic", "indicator": "Author", "front": "Author: unfinished manuscript Remember This House (about Malcolm X, MLK, Medgar Evers) inspired the documentary I Am Not Your Negro directed by Raoul Peck", "back": "James Baldwin", "work": "General / Biographical", "frequency": 6, "tags": []}
  ],
  "cross_refs": []
})

# ============ JOHN CHEEVER ============
write_json("john_cheever", {
  "topic": "John Cheever",
  "summary": "American short story writer and novelist, nicknamed the 'Chekhov of the Suburbs.' Published prolifically in The New Yorker. Known for stories exploring suburban malaise, alcoholism, and the dark underbelly of middle-class life in New England.",
  "works": [
    {"name": "The Swimmer", "indicator": "Short Story", "description": "Cheever's most famous story. Neddy Merrill decides to 'swim' home across his suburban neighborhood by traversing all his neighbors' backyard pools, which he names the 'Lucinda River' after his wife. He begins at the Westerhazys' party on a midsummer day. Along the way he crashes the Biswangers' party (where Grace calls him a 'gate-crasher'), is refused a drink by his former mistress Shirley Adams, and encounters signs of his deteriorating life. He ends the journey in autumn, smelling 'autumnal fragrance' and seeing constellations, only to find his house locked and abandoned.", "clues": [
      {"clue": "Neddy Merrill traverses backyard pools; names them the 'Lucinda River' after his wife", "frequency": 14, "tendency": "giveaway", "examples": ["Neddy Merrill traverses backyard pools", "a man reaches his locked and empty house after traveling home on the 'Lucinda River'"]},
      {"clue": "House is abandoned at the end; begins at the Westerhazys'", "frequency": 10, "tendency": "mid", "examples": ["finds his home abandoned", "begins at a party thrown by the Westerhazys"]},
      {"clue": "Grace calls him a 'gate-crasher' at the Biswangers'; refused drink by Shirley Adams", "frequency": 3, "tendency": "power", "examples": ["Grace calls the protagonist a 'gate-crasher' at the Biswangers' party"]},
      {"clue": "Smells 'autumnal fragrance' and sees constellations at the end", "frequency": 2, "tendency": "power", "examples": ["sees constellations and smells an 'autumnal fragrance' as he finds his home abandoned"]}
    ]},
    {"name": "The Enormous Radio", "indicator": "Short Story", "description": "Jim and Irene Westcott are a middle-class couple. A new radio allows Irene to eavesdrop on her neighbors' private lives — arguments, affairs, domestic abuse. She hears a Chopin prelude interrupted by arguing. Irene becomes distressed by the revelations and concludes 'Life is too terrible, too sordid and awful.' Published in The New Yorker in 1947.", "clues": [
      {"clue": "Irene Westcott uses a magical radio to listen to neighbors' private lives", "frequency": 10, "tendency": "giveaway", "examples": ["Irene Westcott using the title device to listen in on her neighbors", "Irene becomes distressed upon hearing 'demonstrations of indigestion, carnal love, abysmal vanity'"]},
      {"clue": "Chopin prelude interrupted by arguing neighbors", "frequency": 1, "tendency": "power", "examples": ["A Chopin prelude is interrupted by a couple arguing"]},
      {"clue": "'Life is too terrible, too sordid and awful'", "frequency": 1, "tendency": "power", "examples": ["a housewife hysterically concludes, 'Life is too terrible, too sordid and awful'"]}
    ]},
    {"name": "Goodbye, My Brother", "indicator": "Short Story", "description": "The Pommeroy family vacations at their Laud's Head summer home. The pessimistic brother Lawrence (nicknamed 'Tifty') predicts the house will fall into the sea. The narrator hits Lawrence with a root on the beach. Characters dress as football players and brides for a party. The story ends with the narrator watching the naked bodies of his wife and sister walking out of the sea.", "clues": [
      {"clue": "Narrator hits pessimistic brother Lawrence with a root at Laud's Head; 'gloomy son of a bitch'", "frequency": 7, "tendency": "mid", "examples": ["the narrator hits his pessimistic brother Lawrence Pommeroy with a root at their Laud's Head summer home", "the main character remarks to his brother, 'You're a gloomy son of a bitch'"]},
      {"clue": "Characters dress as football players and brides for a party", "frequency": 2, "tendency": "power", "examples": ["the narrator and his wife dress up as a football player and a bride for a party"]}
    ]},
    {"name": "Falconer", "indicator": "Novel", "description": "Cheever's novel inspired by his teaching writing at Sing Sing prison. The convict Ezekiel Farragut is imprisoned for fratricide (killing his brother with a poker) and has a homosexual affair with fellow prisoner Jody. Farragut suffers from methadone withdrawal.", "clues": [
      {"clue": "Ezekiel Farragut imprisoned for fratricide; affair with Jody; inspired by Sing Sing teaching", "frequency": 7, "tendency": "mid", "examples": ["a heroin addict is sent to prison for fratricide, where he engages in an affair with Jody", "this author taught writing classes at Sing Sing"]},
    ]},
    {"name": "The Wapshot Chronicle", "indicator": "Novel", "description": "Cheever's first novel, set in the New England fishing town of St. Botolphs. The family includes the father Leander (a retired captain who lost his ship the Topaze), sons Moses and Coverly (bisexual), and their aunt Honora. Leander drowns himself and leaves a letter titled 'Advice to my sons.' Sarah converts the wrecked Topaze into 'The Only Floating Gift Shoppe in New England.' The sequel is The Wapshot Scandal.", "clues": [
      {"clue": "Moses, Coverly, and Leander in St. Botolphs; Aunt Honora; the Topaze", "frequency": 8, "tendency": "giveaway", "examples": ["Moses, Coverly, and Leander", "Cousin Honora purchases a boat named the Topaze, causing Moses and Coverly to leave St. Botolphs"]},
      {"clue": "Leander drowns himself; leaves 'Advice to my sons'", "frequency": 2, "tendency": "mid", "examples": ["ends with Coverly discovering a letter titled 'Advice to my sons' by his father Leander, who had drowned himself"]}
    ]},
    {"name": "The Five-Forty-Eight", "indicator": "Short Story", "description": "The story of Blake, a man who mistreated his former secretary Miss Dent. She confronts him at gunpoint on the title commuter train and forces him to put his face in the dirt. The secretary wrote a letter addressed 'Dear Husband' that includes an image of a volcano erupting with blood.", "clues": [
      {"clue": "Miss Dent forces Blake to rub his face in dirt after the train ride; gun", "frequency": 4, "tendency": "mid", "examples": ["a secretary forces her former boss to put his face in the dirt after pulling a gun on him on the train", "Blake being forced to rub his face in the dirt after getting off the title train"]},
    ]},
    {"name": "The Country Husband", "indicator": "Short Story", "description": "Francis Weed's plane crash-lands in a cornfield at the story's opening. He falls in love with the babysitter in the fictional suburb of Shady Hill. Set in Shady Hill, where Johnny Hake is the title 'housebreaker' of another collection.", "clues": [
      {"clue": "Francis Weed's plane lands in cornfield; loves the babysitter; set in Shady Hill", "frequency": 3, "tendency": "mid", "examples": ["opens with a plane landing in a cornfield and centers on Francis Weed's love for a babysitter", "Francis Moon fantasizes about a babysitter in this author's story 'The Country Husband'"]},
    ]},
    {"name": "General / Biographical", "indicator": "Author", "description": "Cheever is nicknamed the 'Chekhov of the Suburbs.' He was an alcoholic and taught at the Iowa Writers' Workshop (alongside Raymond Carver) and at Sing Sing. He published many stories in The New Yorker. Colm Toibin wrote about him in New Ways to Kill Your Mother. His other works include Bullet Park (featuring Hammer and Nailles) and Oh What a Paradise It Seems.", "clues": [
      {"clue": "'Chekhov of the Suburbs'", "frequency": 4, "tendency": "giveaway", "examples": ["the 'Chekhov of the Suburbs'", "often called the 'Chekhov' of these areas"]},
      {"clue": "Alcoholic; taught at Iowa Writers' Workshop with Raymond Carver", "frequency": 3, "tendency": "mid", "examples": ["This alcoholic author", "Raymond Carver recalled how he and this author spent all of their time at the Iowa Writers' Workshop getting wasted"]},
      {"clue": "Published in The New Yorker", "frequency": 3, "tendency": "giveaway", "examples": ["wrote short stories for the New Yorker"]}
    ]}
  ],
  "comprehensive_summary": "John Cheever, the 'Chekhov of the Suburbs,' is one of the most frequently clued American short story writers. An alcoholic who taught at the Iowa Writers' Workshop (alongside Raymond Carver) and at Sing Sing prison, he published prolifically in The New Yorker.\n\n'The Swimmer' is his most famous story: Neddy Merrill traverses his suburban neighbors' pools, naming them the 'Lucinda River' after his wife. Beginning at the Westerhazys' party, he encounters signs of his decline — Grace calls him a 'gate-crasher' at the Biswangers', his former mistress Shirley Adams refuses him — before arriving home to find his house locked and abandoned, smelling autumn fragrances under constellations.\n\n'The Enormous Radio' depicts Irene Westcott eavesdropping on neighbors through a magical radio, hearing their arguments, affairs, and misery. 'Goodbye, My Brother' follows the Pommeroy family vacation at Laud's Head, where the narrator hits the pessimistic Lawrence with a root on the beach. 'The Five-Forty-Eight' features Miss Dent forcing her abusive former boss Blake to put his face in the dirt at gunpoint.\n\nFalconer, inspired by his Sing Sing teaching, follows Ezekiel Farragut, imprisoned for fratricide, who has an affair with Jody. The Wapshot Chronicle, his first novel, is set in St. Botolphs with the family of Moses, Coverly, and the retired captain Leander. Other works include Bullet Park, 'The Country Husband' (set in Shady Hill), and Oh What a Paradise It Seems.",
  "recursive_suggestions": [],
  "links": [
    {"text": "John Cheever — Wikipedia", "url": "https://en.wikipedia.org/wiki/John_Cheever"},
    {"text": "The Swimmer — Wikipedia", "url": "https://en.wikipedia.org/wiki/The_Swimmer_(short_story)"},
    {"text": "The Enormous Radio — Wikipedia", "url": "https://en.wikipedia.org/wiki/The_Enormous_Radio"}
  ],
  "category": "Literature", "subcategory": "American Literature",
  "year": 1912, "continent": "North America", "country": "United States",
  "tags": [],
  "cards": [
    {"type": "basic", "indicator": "Short Story", "front": "Short Story: the protagonist traverses suburban backyard pools he names the 'Lucinda River' after his wife, arriving home to find his house locked and abandoned", "back": "The Swimmer (John Cheever)", "work": "The Swimmer", "frequency": 14, "tags": []},
    {"type": "basic", "indicator": "Short Story", "front": "Short Story: Irene Westcott uses a magical radio to eavesdrop on her neighbors' arguments, affairs, and misery", "back": "The Enormous Radio (John Cheever)", "work": "The Enormous Radio", "frequency": 10, "tags": []},
    {"type": "basic", "indicator": "Short Story", "front": "Short Story: the narrator hits his pessimistic brother Lawrence with a root on the beach at Laud's Head; characters dress as football players and brides", "back": "Goodbye, My Brother (John Cheever)", "work": "Goodbye, My Brother", "frequency": 7, "tags": []},
    {"type": "basic", "indicator": "Novel", "front": "Novel: Ezekiel Farragut is imprisoned for killing his brother with a poker; has a homosexual affair with Jody; inspired by the author teaching at Sing Sing", "back": "Falconer (John Cheever)", "work": "Falconer", "frequency": 7, "tags": []},
    {"type": "basic", "indicator": "Novel", "front": "Novel: set in St. Botolphs; Moses, Coverly, and retired captain Leander; Aunt Honora; the ship Topaze", "back": "The Wapshot Chronicle (John Cheever)", "work": "The Wapshot Chronicle", "frequency": 8, "tags": []},
    {"type": "basic", "indicator": "Short Story", "front": "Short Story: Miss Dent confronts her abusive former boss Blake at gunpoint on a commuter train and forces him to rub his face in the dirt", "back": "The Five-Forty-Eight (John Cheever)", "work": "The Five-Forty-Eight", "frequency": 4, "tags": []},
    {"type": "basic", "indicator": "Short Story", "front": "Short Story: Francis Weed's plane crash-lands in a cornfield; he falls in love with the babysitter in the suburb of Shady Hill", "back": "The Country Husband (John Cheever)", "work": "The Country Husband", "frequency": 3, "tags": []}
  ],
  "cross_refs": []
})

# Continue with remaining authors in next batch...
# KATE CHOPIN, TENNESSEE WILLIAMS, ARTHUR MILLER, JOAN DIDION

# ============ KATE CHOPIN ============
write_json("kate_chopin", {
  "topic": "Kate Chopin",
  "summary": "American author of French Creole heritage, born Katherine O'Flaherty. Known for proto-feminist fiction set in Louisiana exploring women's autonomy, race relations, and Creole/Acadian culture.",
  "works": [
    {"name": "The Awakening", "indicator": "Novel", "description": "Chopin's most famous work. Edna Pontellier discovers her identity while vacationing on Grand Isle in Louisiana. She has an affair with Robert Lebrun, breaks a glass vase, stomps on her wedding ring, learns to paint, and moves into the 'pigeon house.' Robert leaves a note reading 'Good-by — because I love you.' A crippled bird flutters overhead at the novel's end, mirroring the opening parrot squawking 'Allez vous-en!' Edna ultimately drowns herself in the Gulf of Mexico. The pianist Mademoiselle Reisz is a key figure. Gouvernail appears here and in other stories.", "clues": [
      {"clue": "Edna Pontellier drowns herself in the Gulf of Mexico", "frequency": 12, "tendency": "giveaway", "examples": ["Edna Pontellier drowns herself in the Gulf of Mexico", "the drowning suicide of Edna Pontellier"]},
      {"clue": "Parrot squawks 'Allez vous-en!' at opening; crippled bird at the end", "frequency": 4, "tendency": "mid", "examples": ["begins with a parrot shouting 'Allez vous-en!'", "A crippled bird flutters overhead at the end"]},
      {"clue": "Robert Lebrun; note 'Good-by — because I love you'; 'pigeon house'", "frequency": 4, "tendency": "mid", "examples": ["a note reading 'Good-by - because I love you' in the 'pigeon house,' written by her lover Robert Lebrun"]},
      {"clue": "Edna breaks glass vase, stomps wedding ring, learns to paint", "frequency": 2, "tendency": "power", "examples": ["that woman breaks a glass vase and stomps on her wedding ring before learning to paint"]},
      {"clue": "Mademoiselle Reisz the pianist; set on Grand Isle", "frequency": 2, "tendency": "mid", "examples": ["befriends the old pianist Mademoiselle Reisz", "vacationing on Grand Isle in Louisiana"]}
    ]},
    {"name": "Desiree's Baby", "indicator": "Short Story", "description": "A story about race in Creole Louisiana. Armand Aubigny, owner of L'Abri, marries the foundling Desiree. When their baby resembles a 'quadroon' boy fanning him with peacock feathers, Armand banishes Desiree and the baby. Desiree disappears into the bayou. At the end, Armand discovers from his mother's letter that it is he, not Desiree, who has Black ancestry. He burns a willow cradle and the letter. Madame Valmonde adopted Desiree; the wet nurse is Zandrine.", "clues": [
      {"clue": "Armand discovers he (not Desiree) has Black ancestry from his mother's letter; burns cradle", "frequency": 10, "tendency": "giveaway", "examples": ["Armand Aubigny, who learns about his black ancestry", "it is revealed that Armand, not Desiree, has African heritage"]},
      {"clue": "Baby resembles the 'quadroon' boy fanning with peacock feathers", "frequency": 4, "tendency": "mid", "examples": ["she notices the similarities between a baby and a boy fanning him with peacock feathers"]},
      {"clue": "Desiree disappears into the bayou", "frequency": 3, "tendency": "mid", "examples": ["The title woman vanishes into the bayou"]},
      {"clue": "Armand owns L'Abri; fell in love 'as if struck by a pistol shot'", "frequency": 2, "tendency": "power", "examples": ["The owner of the L'Abri estate", "A man falls in love with a girl 'as if struck by a pistol shot'"]}
    ]},
    {"name": "The Story of an Hour", "indicator": "Short Story", "description": "Only six paragraphs long. Louise Mallard hears from Josephine that her husband Brently has died in a railroad accident. She observes the 'delicious breath of rain' and whispers 'free, free, free!' and 'body and soul free!' When Brently returns alive, Louise dies of what doctors call 'the joy that kills' (actually shock).", "clues": [
      {"clue": "Louise whispers 'free, free, free!' after learning husband Brently died; dies of shock when he returns", "frequency": 7, "tendency": "giveaway", "examples": ["resolves to 'live for herself' before she dies of shock when Brently Mallard comes home", "she had died of heart disease--of the joy that kills"]},
      {"clue": "'Delicious breath of rain'; Josephine delivers the news", "frequency": 2, "tendency": "power", "examples": ["observes the 'delicious breath of rain' after hearing news from Josephine"]}
    ]},
    {"name": "A Pair of Silk Stockings", "indicator": "Short Story", "description": "Mrs. Sommers finds herself with fifteen dollars she intended to spend on her children. Instead, she buys silk stockings, kid gloves, has lunch at a restaurant, and attends a matinee. She tips a waiter who bows to her 'as before a princess of royal blood.' The story ends with her wishing the cable car 'would never stop.'", "clues": [
      {"clue": "Mrs. Sommers spends fifteen dollars on herself (stockings, gloves, matinee) instead of her children", "frequency": 4, "tendency": "mid", "examples": ["Mrs. Sommers, who spends fifteen dollars on herself instead of her children", "squanders the money she'd meant to spend on her children"]},
      {"clue": "Wishes the cable car would never stop", "frequency": 2, "tendency": "power", "examples": ["wishes that her 'cable car would never stop'"]}
    ]},
    {"name": "The Storm", "indicator": "Short Story", "description": "A sequel to 'At the 'Cadian Ball' depicting a sexual encounter between Alcee and Calixta during a storm. At the end, Alcee writes a letter to his wife. Chopin's depiction of the Louisiana Acadians (Cajuns) appears in both stories and in her collection A Night in Acadie.", "clues": [
      {"clue": "Alcee and Calixta's affair during a storm; sequel to 'At the 'Cadian Ball'", "frequency": 3, "tendency": "mid", "examples": ["a sexual encounter between Alcee and Calixta in her story 'The Storm'", "At the end of 'The Storm,' Alce goes home and writes a letter"]}
    ]},
    {"name": "At Fault", "indicator": "Novel", "description": "Chopin's first novel about the tangled love between the young Creole Therese Lafirme and the sawmill manager David Hosmer. Fanny drowns while scavenging for alcohol in a riverside cabin.", "clues": [
      {"clue": "Therese and David; Fanny drowns scavenging for alcohol", "frequency": 2, "tendency": "power", "examples": ["Fanny drowns while scavenging for alcohol in a riverside cabin", "The sawmill manager David pursues Therese in this author's first novel, At Fault"]}
    ]},
    {"name": "General / Biographical", "indicator": "Author", "description": "Chopin was born Katherine O'Flaherty and had French Creole heritage. She lived in New Orleans and set many works in Louisiana. Her story collections include Bayou Folk and A Night in Acadie. She was called a 'rogue in porcelain' by Emily Toth. She is considered an early feminist writer. The recurring character Gouvernail appears in 'Athenaise,' 'A Respectable Woman,' and The Awakening.", "clues": [
      {"clue": "French Creole heritage; set works in Louisiana/New Orleans", "frequency": 3, "tendency": "mid", "examples": ["This author's French Creole heritage informed her depiction of Louisiana Acadians"]},
      {"clue": "Collections: Bayou Folk, A Night in Acadie", "frequency": 2, "tendency": "mid", "examples": ["this author, who included 'Desiree's Baby' in Bayou Folk"]},
      {"clue": "Proto-feminist; considered early feminist writer", "frequency": 2, "tendency": "giveaway", "examples": ["this American protofeminist"]}
    ]}
  ],
  "comprehensive_summary": "Kate Chopin (born Katherine O'Flaherty) is a proto-feminist American author of French Creole heritage, known for fiction set in Louisiana exploring women's autonomy, race, and Creole/Acadian culture.\n\nThe Awakening is her most famous work. Edna Pontellier discovers her identity while vacationing on Grand Isle, has an affair with Robert Lebrun, breaks a vase, stomps on her wedding ring, learns to paint, and moves into the 'pigeon house.' The novel opens with a parrot squawking 'Allez vous-en!' and ends with Edna drowning herself in the Gulf of Mexico as a crippled bird flutters overhead. Key figures include the pianist Mademoiselle Reisz and the recurring character Gouvernail.\n\n'Desiree's Baby' explores race in Creole Louisiana. Armand Aubigny banishes his wife Desiree and their baby when the child resembles a quadroon boy, but discovers from his mother's letter that he himself has Black ancestry. Desiree vanishes into the bayou.\n\n'The Story of an Hour' is her most concise masterpiece: Louise Mallard whispers 'free, free, free!' after hearing her husband died in a railroad accident, then dies of shock ('the joy that kills') when he returns alive. 'A Pair of Silk Stockings' follows Mrs. Sommers spending $15 on herself instead of her children. 'The Storm' depicts Alcee and Calixta's affair, a sequel to 'At the 'Cadian Ball.' At Fault is her first novel about Therese and David. Her story collections include Bayou Folk and A Night in Acadie.",
  "recursive_suggestions": [],
  "links": [
    {"text": "Kate Chopin — Wikipedia", "url": "https://en.wikipedia.org/wiki/Kate_Chopin"},
    {"text": "The Awakening — Wikipedia", "url": "https://en.wikipedia.org/wiki/The_Awakening_(Chopin_novel)"},
    {"text": "Desiree's Baby — Wikipedia", "url": "https://en.wikipedia.org/wiki/D%C3%A9sir%C3%A9e%27s_Baby"}
  ],
  "category": "Literature", "subcategory": "American Literature",
  "year": 1850, "continent": "North America", "country": "United States",
  "tags": ["Feminism", "Regionalism"],
  "cards": [
    {"type": "basic", "indicator": "Novel", "front": "Novel: opens with a parrot squawking 'Allez vous-en!'; the protagonist breaks a glass vase, stomps on her wedding ring, and moves into the 'pigeon house' before drowning herself in the Gulf of Mexico", "back": "The Awakening (Kate Chopin)", "work": "The Awakening", "frequency": 12, "tags": []},
    {"type": "basic", "indicator": "Short Story", "front": "Short Story: Armand banishes his wife and baby, but discovers from his mother's letter that it is he who has Black ancestry; the baby resembles a 'quadroon' boy fanning with peacock feathers", "back": "Desiree's Baby (Kate Chopin)", "work": "Desiree's Baby", "frequency": 10, "tags": []},
    {"type": "basic", "indicator": "Short Story", "front": "Short Story: a woman whispers 'free, free, free!' after hearing her husband died in a railroad accident, then dies of 'the joy that kills' when he returns alive", "back": "The Story of an Hour (Kate Chopin)", "work": "The Story of an Hour", "frequency": 7, "tags": []},
    {"type": "basic", "indicator": "Short Story", "front": "Short Story: Mrs. Sommers spends fifteen dollars on silk stockings and a matinee instead of clothes for her children; wishes the cable car would never stop", "back": "A Pair of Silk Stockings (Kate Chopin)", "work": "A Pair of Silk Stockings", "frequency": 4, "tags": []}
  ],
  "cross_refs": []
})

# ============ TENNESSEE WILLIAMS ============
write_json("tennessee_williams", {
  "topic": "Tennessee Williams",
  "summary": "American playwright (born Thomas Lanier Williams III), one of the most important dramatists of the 20th century. His mentally ill sister Rose inspired many of his female characters. Known for lyrical, emotionally intense plays set in the American South.",
  "works": [
    {"name": "A Streetcar Named Desire", "indicator": "Play", "description": "Set on Elysian Fields in New Orleans. Blanche DuBois arrives at her sister Stella's home after losing the family plantation Belle Reve. Blanche's husband Allan Grey committed suicide after she discovered his homosexual affair. She clashes with Stanley Kowalski. The Varsouviana Polka plays in Blanche's mind. She declares 'I don't want realism. I want magic!' Stanley rips a paper lantern to reveal her face. The play ends with Blanche being taken to an institution, saying 'I have always depended upon the kindness of strangers.' The original title referenced poker. Williams wrote 'The Catastrophe of Success' about The Glass Menagerie's success shortly before this play's premiere.", "clues": [
      {"clue": "Blanche DuBois vs Stanley Kowalski on Elysian Fields in New Orleans", "frequency": 10, "tendency": "giveaway", "examples": ["the clash between Blanche DuBois and Stanley Kowalski", "a street in New Orleans which is named Elysian Fields"]},
      {"clue": "Blanche lost Belle Reve; husband Allan Grey's suicide after homosexuality discovered", "frequency": 4, "tendency": "mid", "examples": ["her husband commits suicide when his homosexuality is discovered, and that protagonist loses Belle Reve"]},
      {"clue": "'I don't want realism, I want magic!'; Stanley rips paper lantern", "frequency": 2, "tendency": "mid", "examples": ["a woman who cries, 'I don't want realism. I want magic!' after a man rips a paper lantern"]},
      {"clue": "Varsouviana Polka plays in Blanche's mind", "frequency": 2, "tendency": "power", "examples": ["the Varsouviana Polka plays after a woman confronts her husband about his affair"]},
      {"clue": "'I have always depended upon the kindness of strangers'", "frequency": 1, "tendency": "giveaway", "examples": ["Vivien Leigh's line 'I have always depended upon the kindness of strangers'"]}
    ]},
    {"name": "The Glass Menagerie", "indicator": "Play", "description": "A memory play narrated by Tom Wingfield, who describes the fire escape as 'a structure whose name is a touch of accidental poetic truth.' Amanda Wingfield, the mother, reminisces about gentlemen callers. Laura Wingfield (nicknamed 'Blue Roses' by Jim, the gentleman caller) secretly quit business college after a breakdown during typing class. Laura's collection of glass figurines gives the play its title. Williams's sister Rose inspired Laura. Tom says he 'didn't go to the moon' but 'much further, because time is the longest distance between places.' Williams wrote 'The Catastrophe of Success' about this play's popularity.", "clues": [
      {"clue": "Memory play; Tom Wingfield narrates; Laura nicknamed 'Blue Roses'; gentleman caller Jim", "frequency": 10, "tendency": "giveaway", "examples": ["a girl nicknamed 'Blue Roses' who hosts the 'gentleman caller' Jim", "a woman secretly quits business college after having a breakdown during a typing class"]},
      {"clue": "Amanda Wingfield reminisces about gentlemen callers; 'memory is seated predominantly in the heart'", "frequency": 3, "tendency": "mid", "examples": ["the Wingfield family", "memory is seated predominantly in the heart"]},
      {"clue": "Williams's sister Rose inspired Laura; fire escape described poetically", "frequency": 3, "tendency": "mid", "examples": ["this playwright's mentally ill sister Rose was the basis for many of his female characters", "described a fire escape as 'a structure whose name is a touch of accidental poetic truth'"]},
      {"clue": "'The Catastrophe of Success' essay; Tom says he went 'further' than the moon", "frequency": 2, "tendency": "power", "examples": ["a character who claims that he 'didn't go to the moon,' but much further"]},
      {"clue": "Laura bends over to blow out candles at the end", "frequency": 1, "tendency": "power", "examples": ["Directions at the end describe a girl bending over to blow out some candles"]}
    ]},
    {"name": "Cat on a Hot Tin Roof", "indicator": "Play", "description": "Brick Pollitt drinks until he hears a 'click' and rants about 'mendacity.' His leg injury from hurdling keeps him on a crutch. His wife Maggie ('the Cat') is determined to conceive so they can inherit from the dying Big Daddy Pollitt. Brick's relationship with his deceased friend Skipper is questioned. Gooper and Mae ('Sister Woman' and 'Brother Man') and their 'no-neck monster' children compete for the inheritance. The bed belonged to Jack Straw and Peter Ochello. Maggie carries a Diana Trophy from an archery championship.", "clues": [
      {"clue": "Brick drinks until 'click'; crutch; rants about 'mendacity'; relationship with Skipper questioned", "frequency": 8, "tendency": "giveaway", "examples": ["a character who drinks until he hears a 'click'", "Brick and Big Daddy rail against 'mendacity'"]},
      {"clue": "Maggie the Cat; Big Daddy dying; Gooper and Mae ('no-neck monsters')", "frequency": 5, "tendency": "mid", "examples": ["the nicknames 'Sister Woman' and 'Brother Man' are used for a pair of characters whose children are referred to as 'no-neck monsters'"]},
      {"clue": "Diana Trophy; bed belonged to Jack Straw and Peter Ochello", "frequency": 2, "tendency": "power", "examples": ["a character carries a 'Diana Trophy' that she won in an intercollegiate archery championship", "a bed that used to belong to Jack Straw and Peter Ochello"]},
      {"clue": "Maggie hurls Brick's crutch; determined to 'make that lie come true'", "frequency": 1, "tendency": "power", "examples": ["the crutch is hurled over the rail by its owner's wife"]}
    ]},
    {"name": "Suddenly, Last Summer", "indicator": "Play", "description": "Violet Venable offers a bribe to Dr. Cukrowicz to lobotomize her niece Catherine Holly, who witnessed her son Sebastian's death. Sebastian was a gay poet who was killed and eaten by cannibals (young boys) after watching flesh-eating birds devour sea turtles on the Galapagos (inspired by Melville's 'The Encantadas'). Violet wants to suppress the truth. Sebastian kept a bound collection of twenty poems. Gore Vidal wrote the screenplay adaptation.", "clues": [
      {"clue": "Sebastian killed by cannibals; Catherine reveals the truth; Violet wants lobotomy", "frequency": 7, "tendency": "mid", "examples": ["a woman who tells the story of a gay man who was killed by cannibals", "Violet threatens to lobotomize Catherine Holly"]},
      {"clue": "Sebastian watched sea turtles devoured by birds on the Galapagos (Melville's 'Encantadas')", "frequency": 2, "tendency": "power", "examples": ["sea turtles whose slaughter by 'flesh-eating birds' foreshadows Sebastian's murder"]},
      {"clue": "Gore Vidal wrote screenplay; Sebastian's twenty bound poems", "frequency": 2, "tendency": "power", "examples": ["Gore Vidal wrote the screenplay adaptation"]}
    ]},
    {"name": "The Night of the Iguana", "indicator": "Play", "description": "The defrocked Reverend T. Lawrence Shannon works as a tour guide at a Mexican hotel run by Maxine Faulk. Hannah Jelkes arrives with her nonagenarian poet grandfather Nonno, who is working on his last poem ('How calmly does the orange branch / Observe the sky begin to blanch'). Shannon is accused of statutory rape of Charlotte Goodall. He exclaims 'Don't! Break! Human! Pride!' The title iguana is tied to a pole by Mexicans.", "clues": [
      {"clue": "Rev. Shannon at Maxine Faulk's Mexican hotel; Hannah Jelkes; grandfather Nonno the poet", "frequency": 8, "tendency": "giveaway", "examples": ["the defrocked Reverend Shannon arrives at the Costa Verde Hotel in Mexico as a tourist guide", "Hannah Jelkes, who is travelling with her old grandfather Nonno"]},
      {"clue": "Nonno's last poem: 'How calmly does the orange branch / Observe the sky begin to blanch'", "frequency": 2, "tendency": "power", "examples": ["an author recites his last poem, which begins 'How calmly does the orange branch'"]},
      {"clue": "Shannon accused of statutory rape of Charlotte Goodall", "frequency": 2, "tendency": "mid", "examples": ["accused of raping Charlotte Goodall"]}
    ]},
    {"name": "Summer and Smoke", "indicator": "Play", "description": "Set in Glorious Hill, Mississippi. Centers on the failed romance between Alma Winemiller (a minister's daughter) and the doctor John Buchanan. They end up switching philosophies by the play's end. A key scene has John gesturing to an anatomy chart and challenging Alma to point out the soul. Revised as The Eccentricities of the Nightingale. Title from a Hart Crane poem.", "clues": [
      {"clue": "Alma Winemiller and John Buchanan; anatomy chart/soul scene; they switch philosophies", "frequency": 4, "tendency": "mid", "examples": ["the failed romance between Alma Winemiller and John Buchanan", "a doctor gestures to an anatomy chart on his wall and challenges his love interest to point out the soul"]},
      {"clue": "Revised as The Eccentricities of the Nightingale; title from Hart Crane", "frequency": 2, "tendency": "power", "examples": ["Reworked into The Eccentricities of the Nightingale"]}
    ]},
    {"name": "Sweet Bird of Youth", "indicator": "Play", "description": "Features the aging actress Princess Kosmonopolis and the gigolo Chance Wayne, who faces punishment from the politician Boss Finley. The play contrasts a drug addict's return to Hollywood fame with the protagonist's punishment.", "clues": [
      {"clue": "Princess Kosmonopolis; gigolo Chance Wayne; Boss Finley", "frequency": 4, "tendency": "mid", "examples": ["an aging actress using the name 'Princess Kosmonopolis'", "a play featuring the actress Princess Kosmonopolis and the politician Boss Finley"]}
    ]},
    {"name": "The Rose Tattoo", "indicator": "Play", "description": "Set among Sicilian-Americans. A condom falling from a man's pocket caused controversy. Alvaro Mangiacavallo reveals a copy of the title rose tattoo on his chest to the widow Serafina, beginning a relationship. Serafina discovers her late husband had an affair with Estelle Hohengarten. A septet of mannequins includes a bride and widow facing each other.", "clues": [
      {"clue": "Alvaro and Serafina; condom falls from pocket; rose tattoo on his chest; mannequins", "frequency": 4, "tendency": "mid", "examples": ["Alvaro Mangiacavallo begins a relationship with the Sicilian woman Serafina", "a condom falls out of a man's pocket"]}
    ]},
    {"name": "Orpheus Descending", "indicator": "Play", "description": "Reworked from Williams's earlier Battle of Angels. Val (representing Orpheus) arrives in town and falls in love with Lady Torrance. Jabe (Lady's jealous husband) shoots her, and Val dies in a fire. Carol remarks that 'wild things leave skins behind them.'", "clues": [
      {"clue": "Reworked from Battle of Angels; Val and Lady; Val dies in a fire; Orpheus retelling", "frequency": 4, "tendency": "mid", "examples": ["reworked the play Battle of Angels into Orpheus Descending", "Val, who dies in a fire set by Lady Torrance's jealous husband"]}
    ]},
    {"name": "General / Biographical", "indicator": "Author", "description": "Born Thomas Lanier Williams III. His mentally ill sister Rose inspired many female characters (Laura Wingfield, etc.). He wrote 'The Catastrophe of Success' after The Glass Menagerie's success. He wrote the essay beginning 'the Cinderella story is America's national myth.' Carson McCullers was a close friend. He traveled to Cuba to meet Hemingway. Colm Toibin wrote about him. He adapted Chekhov's The Seagull into The Notebook of Trigorin. Marlon Brando starred in both stage and film versions of Streetcar.", "clues": [
      {"clue": "Sister Rose inspired many female characters", "frequency": 4, "tendency": "mid", "examples": ["this playwright's mentally ill sister Rose was the basis for many of his female characters"]},
      {"clue": "'The Catastrophe of Success' essay", "frequency": 3, "tendency": "mid", "examples": ["wrote 'The Catastrophe of Success' three years after the Chicago opening of The Glass Menagerie"]},
      {"clue": "Adapted Chekhov's Seagull as The Notebook of Trigorin", "frequency": 1, "tendency": "power", "examples": ["adapted Anton Chekhov's The Seagull into his play The Notebook of Trigorin"]}
    ]}
  ],
  "comprehensive_summary": "Tennessee Williams (Thomas Lanier Williams III) is one of the most frequently clued American playwrights. His mentally ill sister Rose inspired many of his female characters, and his plays are known for their lyrical stage directions and emotionally devastating Southern settings.\n\nA Streetcar Named Desire is set on Elysian Fields in New Orleans, depicting Blanche DuBois's clash with her sister Stella's husband Stanley Kowalski. Blanche lost Belle Reve and her husband Allan Grey killed himself after she discovered his homosexuality. The Varsouviana Polka haunts her, she declares 'I don't want realism, I want magic!', and she ends up institutionalized saying 'I have always depended upon the kindness of strangers.'\n\nThe Glass Menagerie is a memory play narrated by Tom Wingfield about his sister Laura ('Blue Roses') and her glass collection. Laura quit business college after a breakdown during typing class. Williams wrote 'The Catastrophe of Success' about this play.\n\nCat on a Hot Tin Roof centers on Brick Pollitt's alcoholism, his rants about 'mendacity,' and his complicated relationship with the deceased Skipper. Maggie the Cat and Big Daddy Pollitt struggle over the inheritance.\n\nSuddenly, Last Summer features Catherine Holly's revelation that her cousin Sebastian was killed and eaten by cannibals. The Night of the Iguana follows defrocked Rev. Shannon at a Mexican hotel with Hannah Jelkes and her poet grandfather Nonno. Summer and Smoke depicts the philosophical reversal between Alma Winemiller and John Buchanan. Other key works include Sweet Bird of Youth, The Rose Tattoo, and Orpheus Descending.",
  "recursive_suggestions": [],
  "links": [
    {"text": "Tennessee Williams — Wikipedia", "url": "https://en.wikipedia.org/wiki/Tennessee_Williams"},
    {"text": "A Streetcar Named Desire — Wikipedia", "url": "https://en.wikipedia.org/wiki/A_Streetcar_Named_Desire"},
    {"text": "The Glass Menagerie — Wikipedia", "url": "https://en.wikipedia.org/wiki/The_Glass_Menagerie"},
    {"text": "Cat on a Hot Tin Roof — Wikipedia", "url": "https://en.wikipedia.org/wiki/Cat_on_a_Hot_Tin_Roof"}
  ],
  "category": "Literature", "subcategory": "American Literature",
  "year": 1911, "continent": "North America", "country": "United States",
  "tags": ["Southern Gothic"],
  "cards": [
    {"type": "basic", "indicator": "Play", "front": "Play: set on Elysian Fields in New Orleans; protagonist lost Belle Reve and her husband committed suicide after his homosexuality was discovered; she is taken to an institution", "back": "A Streetcar Named Desire (Tennessee Williams)", "work": "A Streetcar Named Desire", "frequency": 10, "tags": []},
    {"type": "basic", "indicator": "Play", "front": "Play: 'I don't want realism, I want magic!'; the Varsouviana Polka plays during a mental breakdown; ends with 'I have always depended upon the kindness of strangers'", "back": "A Streetcar Named Desire (Tennessee Williams)", "work": "A Streetcar Named Desire", "frequency": 2, "tags": []},
    {"type": "basic", "indicator": "Play", "front": "Play: a memory play; a girl nicknamed 'Blue Roses' secretly quit business college after a typing class breakdown; a 'gentleman caller' named Jim visits", "back": "The Glass Menagerie (Tennessee Williams)", "work": "The Glass Menagerie", "frequency": 10, "tags": []},
    {"type": "basic", "indicator": "Play", "front": "Play: an alcoholic drinks until he hears a 'click' in his head; rants about 'mendacity'; his relationship with deceased friend Skipper is questioned", "back": "Cat on a Hot Tin Roof (Tennessee Williams)", "work": "Cat on a Hot Tin Roof", "frequency": 8, "tags": []},
    {"type": "basic", "indicator": "Play", "front": "Play: a mother offers to bribe a doctor to lobotomize her niece, who witnessed her gay poet son being killed and eaten by cannibals", "back": "Suddenly, Last Summer (Tennessee Williams)", "work": "Suddenly, Last Summer", "frequency": 7, "tags": []},
    {"type": "basic", "indicator": "Play", "front": "Play: a defrocked reverend works as a tour guide at a Mexican hotel run by Maxine Faulk; Hannah Jelkes arrives with her poet grandfather Nonno", "back": "The Night of the Iguana (Tennessee Williams)", "work": "The Night of the Iguana", "frequency": 8, "tags": []},
    {"type": "basic", "indicator": "Play", "front": "Play: the failed romance between Alma Winemiller and John Buchanan; a doctor challenges his love interest to find the soul on an anatomy chart", "back": "Summer and Smoke (Tennessee Williams)", "work": "Summer and Smoke", "frequency": 4, "tags": []},
    {"type": "basic", "indicator": "Play", "front": "Play: a condom falls from a man's pocket; Alvaro reveals a tattoo matching the late husband's; Serafina discovers her husband's affair with Estelle", "back": "The Rose Tattoo (Tennessee Williams)", "work": "The Rose Tattoo", "frequency": 4, "tags": []}
  ],
  "cross_refs": []
})

# ============ ARTHUR MILLER ============
write_json("arthur_miller", {
  "topic": "Arthur Miller",
  "summary": "American playwright, one of the most important dramatists of the 20th century. Known for plays examining the American Dream, moral responsibility, and McCarthyism. Married to Marilyn Monroe.",
  "works": [
    {"name": "Death of a Salesman", "indicator": "Play", "description": "Miller's most famous play about Willy Loman, a traveling salesman in decline. His son Biff was a high school football star who dropped out after discovering Willy's affair with a woman in a Boston hotel room. Biff steals a pen from Bill Oliver. Willy's other son is Happy. Willy reminisces about his brother Ben who struck it rich in Alaska. He is denied a desk job by his boss Howard Wagner ('You can't eat the orange and throw the peel away'). Bernard, the studious neighbor boy, later becomes successful. Willy kills himself for the life insurance money. Jo Mielziner designed the set with semi-transparent walls.", "clues": [
      {"clue": "Willy Loman; Biff discovered father's affair in Boston; steals pen from Bill Oliver", "frequency": 10, "tendency": "giveaway", "examples": ["whose football star son dropped out of school after seeing him with a mistress in a Boston hotel room", "Biff steals this object after Bill Oliver fails to remember him"]},
      {"clue": "Willy denied desk job by Howard Wagner; 'you can't eat the orange and throw the peel away'", "frequency": 2, "tendency": "mid", "examples": ["'You can't eat the orange and throw the peel away - a man is not a piece of fruit!'"]},
      {"clue": "Willy's brother Ben struck it rich in Alaska; Willy kills himself for insurance", "frequency": 2, "tendency": "mid", "examples": ["the protagonist reminisces about his brother Ben, who struck it rich in Alaska"]},
      {"clue": "Mielziner's set with semi-transparent walls", "frequency": 1, "tendency": "power", "examples": ["Mielziner incorporated semi-transparent walls"]}
    ]},
    {"name": "A View from the Bridge", "indicator": "Play", "description": "Set in Red Hook, Brooklyn ('the Gullet of New York'). The longshoreman Eddie Carbone takes in his wife Beatrice's Italian immigrant cousins Marco and Rodolpho. Eddie becomes obsessively protective of his niece Catherine and reports Marco and Rodolpho to immigration. Act I ends with Marco lifting a chair over Eddie's head with one hand. The Italian lawyer Alfieri narrates and advises characters to 'settle for half.' Eddie is killed by Marco in a knife fight with his own knife. Beatrice tells Eddie he can 'never have' Catherine.", "clues": [
      {"clue": "Eddie Carbone in Red Hook; reports cousins to immigration; Marco lifts chair; Alfieri narrates", "frequency": 10, "tendency": "giveaway", "examples": ["Alfieri narrates this Miller play set in Red Hook, in which the longshoreman Eddie is killed", "Marco holds a chair over Eddie's head after Eddie hits Rodolpho"]},
      {"clue": "Eddie killed by Marco in knife fight; Beatrice says 'never have' Catherine", "frequency": 4, "tendency": "mid", "examples": ["Marco kills Eddie Carbone", "Beatrice says her husband can 'never have' his niece Catherine"]}
    ]},
    {"name": "The Crucible", "indicator": "Play", "description": "About the Salem Witch Trials, widely interpreted as an allegory for McCarthyism. John Proctor is the protagonist, 'a farmer in his middle thirties.' His last words are 'I have given you my soul! Leave me my name!' Thomas Putnam's rivalry drives many accusations. A character gives a pregnant woman a 'poppet' stuck with a needle. The play has extensive narrative interludes providing historical context.", "clues": [
      {"clue": "Salem Witch Trials; John Proctor; 'I have given you my soul! Leave me my name!'", "frequency": 6, "tendency": "giveaway", "examples": ["a play about the Salem Witch Trials by Arthur Miller", "a man is hanged after declaring 'I have given you my soul! Leave me my name.'"]},
      {"clue": "Poppet stuck with a needle; Thomas Putnam", "frequency": 2, "tendency": "mid", "examples": ["a character gives a pregnant woman a 'poppet' stuck with a needle"]},
      {"clue": "Narrative interludes providing historical context (distinct from stage directions)", "frequency": 1, "tendency": "power", "examples": ["works that provide context in a play about the Salem Witch Trials"]}
    ]},
    {"name": "All My Sons", "indicator": "Play", "description": "Joe Keller manufactures faulty airplane cylinder heads that kill 21 pilots, blaming his partner Steve Deever. His son Larry's apple tree blows down. Anne Deever gives Kate a letter revealing Larry's suicide (he suspected his father). Joe kills himself at the end. The neighbor Jim Bayliss says 'once the star of one's honesty goes out, it never comes back.' Frank Lubey constructs horoscopes.", "clues": [
      {"clue": "Joe Keller ships faulty cylinder heads; blames Steve Deever; Larry's suicide letter", "frequency": 6, "tendency": "giveaway", "examples": ["Joe Keller manufactures faulty airplane parts for American soldiers", "a letter reveals the suicide of a World War II pilot"]},
      {"clue": "Larry's apple tree blows down; Joe kills himself", "frequency": 2, "tendency": "mid", "examples": ["the tree which had been planted to mark Larry's death blows down"]},
      {"clue": "Jim Bayliss neighbor; Frank Lubey constructs horoscopes", "frequency": 2, "tendency": "power", "examples": ["Jim Bayliss claims that once the star of one's honesty goes out, it never comes back"]}
    ]},
    {"name": "After the Fall", "indicator": "Play", "description": "Takes place in the mind of Quentin, who interacts with his former wives. The set consists of a chair in front of a concentration camp tower. Quentin's suicidal wife Maggie is a fictionalization of Marilyn Monroe. Lou commits suicide after Mickey 'names names.'", "clues": [
      {"clue": "Set in Quentin's mind; chair and concentration camp tower; Maggie = Marilyn Monroe", "frequency": 5, "tendency": "mid", "examples": ["takes place in the mind of Quentin", "This person is fictionalized as the protagonist's suicidal wife"]},
      {"clue": "Lou's suicide after Mickey 'names names'", "frequency": 1, "tendency": "power", "examples": ["Lou commits suicide after Mickey 'names names'"]}
    ]},
    {"name": "Incident at Vichy", "indicator": "Play", "description": "Set in 1940s France. The psychoanalyst Leduc rallies prisoners. A businessman gives a white pass to Leduc, allowing him to escape the Nazi regime.", "clues": [
      {"clue": "1940s France; Leduc the psychoanalyst; white pass to escape", "frequency": 3, "tendency": "mid", "examples": ["The psychoanalyst Leduc rallies prisoners in a play set in 1940s France", "a businessman gives a white pass to the psychiatrist Leduc"]}
    ]},
    {"name": "General / Biographical", "indicator": "Author", "description": "Miller was married to Marilyn Monroe, which inspired After the Fall and the screenplay The Misfits. He also wrote Resurrection Blues (TV crew films crucifixion), The Price (chairs remind Victor and Walter of their dead father), Broken Glass (woman paralyzed by Kristallnacht news), and The Man Who Had All the Luck (David's mink epiphany).", "clues": [
      {"clue": "Married to Marilyn Monroe; wrote The Misfits screenplay", "frequency": 3, "tendency": "mid", "examples": ["He was one of the husbands of Marilyn Monroe and wrote the screenplay for The Misfits"]},
      {"clue": "Resurrection Blues: TV crew films crucifixion", "frequency": 2, "tendency": "power", "examples": ["a TV crew plans to film the crucifixion of an unseen prisoner in a Latin American country"]}
    ]}
  ],
  "comprehensive_summary": "Arthur Miller is one of the most important American playwrights, known for examining moral responsibility, the American Dream, and political persecution.\n\nDeath of a Salesman follows Willy Loman's decline. His son Biff was a football star who discovered his father's affair in a Boston hotel room and dropped out. Biff steals a pen from Bill Oliver. Willy's boss Howard Wagner denies him a desk job. Willy kills himself for the insurance money.\n\nA View from the Bridge is set in Red Hook, Brooklyn. The longshoreman Eddie Carbone takes in Italian immigrants Marco and Rodolpho, becomes obsessively protective of his niece Catherine, and reports them to immigration. Act I ends with Marco lifting a chair over Eddie's head. The lawyer Alfieri narrates. Eddie dies in a knife fight with Marco.\n\nThe Crucible depicts the Salem Witch Trials as an allegory for McCarthyism. John Proctor's last words are 'I have given you my soul! Leave me my name!' All My Sons features Joe Keller's cover-up of shipping faulty cylinder heads that killed 21 pilots.\n\nAfter the Fall takes place in Quentin's mind before a concentration camp tower; Maggie fictionalizes Marilyn Monroe. Miller also wrote Incident at Vichy, The Price, Broken Glass, and Resurrection Blues.",
  "recursive_suggestions": [],
  "links": [
    {"text": "Arthur Miller — Wikipedia", "url": "https://en.wikipedia.org/wiki/Arthur_Miller"},
    {"text": "Death of a Salesman — Wikipedia", "url": "https://en.wikipedia.org/wiki/Death_of_a_Salesman"},
    {"text": "The Crucible — Wikipedia", "url": "https://en.wikipedia.org/wiki/The_Crucible"},
    {"text": "A View from the Bridge — Wikipedia", "url": "https://en.wikipedia.org/wiki/A_View_from_the_Bridge"}
  ],
  "category": "Literature", "subcategory": "American Literature",
  "year": 1915, "continent": "North America", "country": "United States",
  "tags": [],
  "cards": [
    {"type": "basic", "indicator": "Play", "front": "Play: the protagonist's football star son dropped out of school after discovering his father's affair in a Boston hotel; later steals a pen from Bill Oliver", "back": "Death of a Salesman (Arthur Miller)", "work": "Death of a Salesman", "frequency": 10, "tags": []},
    {"type": "basic", "indicator": "Play", "front": "Play: set in Red Hook, Brooklyn; Act I ends with an immigrant lifting a chair over the protagonist's head with one hand; the lawyer Alfieri narrates", "back": "A View from the Bridge (Arthur Miller)", "work": "A View from the Bridge", "frequency": 10, "tags": []},
    {"type": "basic", "indicator": "Play", "front": "Play: Salem Witch Trials allegory; protagonist's last words are 'I have given you my soul! Leave me my name!'; a poppet stuck with a needle is key evidence", "back": "The Crucible (Arthur Miller)", "work": "The Crucible", "frequency": 6, "tags": []},
    {"type": "basic", "indicator": "Play", "front": "Play: Joe Keller blames partner Steve Deever for shipping faulty cylinder heads that killed 21 pilots; his son Larry's suicide letter reveals the truth", "back": "All My Sons (Arthur Miller)", "work": "All My Sons", "frequency": 6, "tags": []},
    {"type": "basic", "indicator": "Play", "front": "Play: set in the protagonist's mind; a chair before a concentration camp tower; his suicidal wife is based on Marilyn Monroe", "back": "After the Fall (Arthur Miller)", "work": "After the Fall", "frequency": 5, "tags": []}
  ],
  "cross_refs": []
})

# ============ JOAN DIDION ============
write_json("joan_didion", {
  "topic": "Joan Didion",
  "summary": "American essayist, novelist, and screenwriter, a leading figure of New Journalism. Associated with California, 1960s counterculture, and incisive cultural criticism. Known for her grief memoirs after her husband John Gregory Dunne's death.",
  "works": [
    {"name": "Slouching Towards Bethlehem", "indicator": "Work", "description": "Didion's first essay collection, centered on California in the late 1960s. The title essay describes the Haight-Ashbury district in San Francisco during 1967, opening 'The center was not holding.' She follows acid-selling Deadeye and meets a five-year-old girl in 'High Kindergarten' who was given LSD and peyote. The collection includes 'Notes of a Native Daughter' (about Sacramento), 'Some Dreamers of the Golden Dream' (Lucille Miller's murder conviction in San Bernardino), 'John Wayne: A Love Song,' 'On Keeping a Notebook,' and 'Goodbye to All That' (about leaving New York). The sections are 'Life Styles in the Golden Land' and 'Seven Places of the Mind.' The title references a Yeats poem.", "clues": [
      {"clue": "Title essay on Haight-Ashbury; 'the center was not holding'; Deadeye; High Kindergarten girl", "frequency": 10, "tendency": "giveaway", "examples": ["described the Haight-Ashbury district in an essay that opens 'The center was not holding'", "meets a five-year-old girl who claims to be in 'High Kindergarten' after being given acid and peyote"]},
      {"clue": "'Goodbye to All That': leaving New York; 'distinctly possible to stay too long at the Fair'", "frequency": 4, "tendency": "mid", "examples": ["noted how 'six months can become eight years'", "'it is distinctly possible to stay too long at the Fair'"]},
      {"clue": "'Some Dreamers of the Golden Dream': Lucille Miller murder in San Bernardino", "frequency": 2, "tendency": "power", "examples": ["Lucille Maxwell Miller's conviction for murdering her husband in the San Bernardino Valley"]},
      {"clue": "'John Wayne: A Love Song'; 'On Keeping a Notebook'; 'Notes of a Native Daughter'", "frequency": 3, "tendency": "power", "examples": ["visiting the set of The Sons of Elder Katie in 'John Wayne: A Love Song'", "explained that writing down anecdotes helps her reconnect with her past selves in 'On Keeping a Notebook'"]}
    ]},
    {"name": "The White Album", "indicator": "Work", "description": "Didion's second essay collection. The title essay opens 'We tell ourselves stories in order to live' and describes a recording session of The Doors (called 'the Norman Mailers of the Top Forty' and 'missionaries of apocalyptic sex'), conversations with Manson follower Linda Kasabian, and Black Panther meetings. The essay 'In Bed' describes her chronic migraines. 'Many Mansions' discusses Ronald Reagan's mansion. Named after a Beatles album.", "clues": [
      {"clue": "'We tell ourselves stories in order to live' opening; The Doors; Linda Kasabian; Black Panthers", "frequency": 10, "tendency": "giveaway", "examples": ["begins with the phrase, 'We tell ourselves stories in order to live'", "includes interviews with Manson follower Linda Kasabian"]},
      {"clue": "'In Bed' about migraines; named after Beatles album", "frequency": 2, "tendency": "power", "examples": ["In the essay 'In Bed,' the narrator describes their experiences with chronic migraines", "titled after a Beatles album"]}
    ]},
    {"name": "The Year of Magical Thinking", "indicator": "Work", "description": "Didion's grief memoir about the death of her husband John Gregory Dunne, written while their daughter Quintana Roo was hospitalized. The recurring line 'You sit down to dinner and life as you know it ends.' Didion cannot give away her husband's shoes. She uses Auden's 'Funeral Blues' to process grief. The phrase 'life changes fast' anchors the book. Won the National Book Award.", "clues": [
      {"clue": "Grief memoir after John Gregory Dunne's death; 'life changes fast'; Quintana Roo hospitalized", "frequency": 10, "tendency": "giveaway", "examples": ["chronicled life directly following the death of her husband John Gregory Dunne", "'life changes fast' in a book about the death of her husband"]},
      {"clue": "Cannot give away husband's shoes; 'You sit down to dinner and life as you know it ends'", "frequency": 3, "tendency": "mid", "examples": ["Didion is unable to give away these objects belonging to her husband", "'You sit down to dinner and life as you know it ends'"]},
      {"clue": "Uses 'Funeral Blues' by Auden; daughter Quintana Roo", "frequency": 2, "tendency": "mid", "examples": ["described using 'Funeral Blues' to process the death of her husband"]}
    ]},
    {"name": "Play It As It Lays", "indicator": "Novel", "description": "A 1970 novel about the actress Maria Wyeth, who compulsively drives on the freeway. Opens with 'What makes Iago evil?' Maria writes 'NOTHING APPLIES' on a psychological test and ends by saying 'I know what nothing means, and keep on playing.' BZ commits suicide. Didion collaborated with her husband to adapt it into a screenplay. Set in Hollywood.", "clues": [
      {"clue": "Actress Maria Wyeth; compulsive freeway driving; 'What makes Iago evil?'; 'NOTHING APPLIES'", "frequency": 6, "tendency": "mid", "examples": ["a woman writes 'NOTHING APPLIES' on her psychological test", "compulsively drives on the freeway, going nowhere"]},
      {"clue": "BZ's suicide; adapted into screenplay with husband", "frequency": 2, "tendency": "power", "examples": ["BZ's suicide leads Carter's ex-wife Maria to be institutionalised"]}
    ]},
    {"name": "Blue Nights", "indicator": "Work", "description": "A 2011 memoir about the death of Didion's daughter Quintana Roo. Opens with a girl with 'quicksilver changes of mood.' Didion argues with her daughter about reading 'Funeral Blues.' The title refers to the twilight before summer solstice.", "clues": [
      {"clue": "Memoir about daughter Quintana Roo's death; argues about 'Funeral Blues'", "frequency": 3, "tendency": "mid", "examples": ["a 2011 memoir about the death of her daughter Quintana Roo, Blue Nights", "recalls arguing with her daughter about reading 'Funeral Blues'"]}
    ]},
    {"name": "Salvador", "indicator": "Work", "description": "An account of Didion's 1982 trip to El Salvador, where she noted 'to disappear' had become a transitive verb in Spanish.", "clues": [
      {"clue": "1982 trip to El Salvador; 'to disappear' as transitive verb", "frequency": 1, "tendency": "power", "examples": ["considered how 'to disappear' had become a transitive verb in Spanish"]}
    ]},
    {"name": "General / Biographical", "indicator": "Author", "description": "Didion grew up in Sacramento, California. She defined writing as 'a hostile act' in a talk titled after a George Orwell essay ('Why I Write'). She is identified as a New Journalist. She co-wrote screenplays including The Panic in Needle Park and A Star Is Born (1976) with her husband John Gregory Dunne. Her nephew is Griffin Dunne, who directed the documentary The Center Will Not Hold. Harrison Ford attended her Easter parties. She argued for the innocence of the Central Park Five. Eve Babitz was discovered by Didion as a literary talent.", "clues": [
      {"clue": "Californian essayist; New Journalist", "frequency": 4, "tendency": "giveaway", "examples": ["this Californian essayist", "A proponent of New Journalism"]},
      {"clue": "Defined writing as 'a hostile act'; husband John Gregory Dunne", "frequency": 2, "tendency": "mid", "examples": ["defined writing as 'a hostile act'"]},
      {"clue": "Co-wrote screenplays: Panic in Needle Park, A Star Is Born", "frequency": 1, "tendency": "power", "examples": ["co-wrote the screenplays of Al Pacino's breakthrough film, The Panic in Needle Park"]},
      {"clue": "Nephew Griffin Dunne directed The Center Will Not Hold", "frequency": 1, "tendency": "power", "examples": ["a documentary by a relative of this author titled The Center Will Not Hold"]},
      {"clue": "Eve Babitz connection; 'two halves of American womanhood'", "frequency": 2, "tendency": "power", "examples": ["Eve Babitz was discovered as a literary talent by this author"]}
    ]}
  ],
  "comprehensive_summary": "Joan Didion is one of the most important American essayists and a leading figure of New Journalism. Her work explores California, counterculture, grief, and cultural criticism with distinctive prose style.\n\nSlouching Towards Bethlehem, her first essay collection, centers on California in the late 1960s. The title essay (named for a Yeats poem) describes the Haight-Ashbury district, opening 'The center was not holding.' She follows the acid-dealer Deadeye and meets a five-year-old girl in 'High Kindergarten' given LSD. Other essays include 'Goodbye to All That' (leaving New York), 'Some Dreamers of the Golden Dream' (Lucille Miller's murder in San Bernardino), 'John Wayne: A Love Song,' and 'On Keeping a Notebook.'\n\nThe White Album opens with 'We tell ourselves stories in order to live.' It describes The Doors, Linda Kasabian of the Manson family, and Black Panther meetings. Named after a Beatles album, it also contains 'In Bed' about migraines and 'Many Mansions' about Reagan.\n\nThe Year of Magical Thinking chronicles her grief after husband John Gregory Dunne's death while their daughter Quintana Roo was hospitalized. 'Life changes fast' and 'You sit down to dinner and life as you know it ends' recur throughout. She cannot give away his shoes and uses Auden's 'Funeral Blues.' Blue Nights mourns Quintana Roo's death.\n\nPlay It As It Lays follows actress Maria Wyeth who compulsively drives on freeways and writes 'NOTHING APPLIES' on her psychological test. Salvador documents her 1982 El Salvador trip. Didion co-wrote screenplays with Dunne including The Panic in Needle Park and A Star Is Born.",
  "recursive_suggestions": [],
  "links": [
    {"text": "Joan Didion — Wikipedia", "url": "https://en.wikipedia.org/wiki/Joan_Didion"},
    {"text": "Slouching Towards Bethlehem — Wikipedia", "url": "https://en.wikipedia.org/wiki/Slouching_Towards_Bethlehem"},
    {"text": "The White Album — Wikipedia", "url": "https://en.wikipedia.org/wiki/The_White_Album_(book)"},
    {"text": "The Year of Magical Thinking — Wikipedia", "url": "https://en.wikipedia.org/wiki/The_Year_of_Magical_Thinking"}
  ],
  "category": "Literature", "subcategory": "American Literature",
  "year": 1934, "continent": "North America", "country": "United States",
  "tags": ["New Journalism"],
  "cards": [
    {"type": "basic", "indicator": "Work", "front": "Work: title essay opens 'The center was not holding' about San Francisco's Haight-Ashbury; meets a 5-year-old in 'High Kindergarten' given acid; also contains 'Goodbye to All That' and 'Some Dreamers of the Golden Dream'", "back": "Slouching Towards Bethlehem (Joan Didion)", "work": "Slouching Towards Bethlehem", "frequency": 10, "tags": []},
    {"type": "basic", "indicator": "Work", "front": "Work: opens 'We tell ourselves stories in order to live'; describes a Doors recording session and conversations with Manson follower Linda Kasabian; named after a Beatles album", "back": "The White Album (Joan Didion)", "work": "The White Album", "frequency": 10, "tags": []},
    {"type": "basic", "indicator": "Work", "front": "Work: grief memoir about husband's death; 'You sit down to dinner and life as you know it ends'; cannot give away his shoes; daughter Quintana Roo hospitalized", "back": "The Year of Magical Thinking (Joan Didion)", "work": "The Year of Magical Thinking", "frequency": 10, "tags": []},
    {"type": "basic", "indicator": "Novel", "front": "Novel: opens with 'What makes Iago evil?'; the actress protagonist compulsively drives on the freeway; writes 'NOTHING APPLIES' on a psychological test", "back": "Play It As It Lays (Joan Didion)", "work": "Play It As It Lays", "frequency": 6, "tags": []},
    {"type": "basic", "indicator": "Work", "front": "Work: memoir about the author's daughter Quintana Roo's death; recalls arguing about reading 'Funeral Blues'", "back": "Blue Nights (Joan Didion)", "work": "Blue Nights", "frequency": 3, "tags": []}
  ],
  "cross_refs": []
})

print("All remaining JSONs generated!")
