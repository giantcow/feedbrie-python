# FeedBrie
Brie minigame/activity for twitch offline chat

## Idea:
Class pet named Brie (mouse)  
Brie herself can be the bot in chat  
Brie is "asleep" when stream is on  
Students (viewers) have points accumulated through various means  
Brie has certain "affection" towards each student (affection points), everyone starts at 0  
The student with the highest affection value with Brie will be publicly visible and unlock new interactions

There are different commands students can use in offline chat to trigger interactions with Brie
- List the student Brie has the highest affection with
  - maybe can be used when stream is on, but on a long cooldown so not spammable, the bot can say "I'm asleep and dreaming about \<student with highest affection\>" or something like that
  - when stream offline, can respond with "I love \<student\> the most!" or something
- Buy cheese from a "store" using points
- Pat Brie (offers minimal affection bonus, free to use, on a cooldown/limited uses per 24hrs)
- Bellyrub Brie (moderate affection bonus, can only be used after certain affection threshold is met, cooldown/limited uses?)
- Feed Brie (from student's inventory of bought cheeses, affection bonus varies based on cheese type, unlimited use as long as they have cheese available in inventory)
- Hug Brie (high affection bonus, only available after a bigger threshold is met, cooldown/limited uses?)
- Cuddle with Brie (only available to student with highest affection, does not give affection bonus, we can have a range of cute messages that the bot, Brie, will say when this command is used)

There is a "store" where students can purchase different cheeses
- buying cheese should be the primary way to gain big affection bonuses (incentive to get points during stream)
- brie cheese gives highest affection, also most expensive
- we'll have a range of different cheeses at different costs and affection bonuses

Can potentially reset everyone's affection points every month/set interval?

To prevent students from getting discouraged if someone else is vastly in the lead, interacting with Brie and getting to a certain affection level will grant a special item to that student that can be used after affection reset, to provide a small head-start on affection points. (Every student can earn this item)