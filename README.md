# ReplyRobin 
### Side-kick, which quitely drops in draft and learns from you inbox.

As name suggest this is side-kick which quitely sits & learns from your inbox.
No need of custom integration to your data source or any other tedious setup. We are ready, set, go...

ReplyRobin learns from past expericne and your daily interactions (comming soon) and try to guess the best draft possible (this is what LLM essentially do).

### Core Components
- Cron Jobs
    - Fetcher (Fetches all the latest threads into our DB)
    - Processor (Hyradates with stylometery and intent signals on all the messages which are added to our DB)
- Master Agent (Orchestrates and manges all agents)
    - Planner Agent (Plans draft stragy)
    - Drafter Agent (Drafts using contextual email and linguistic profile of the user)
    - Judge Agent (Judges the draft based on various signals such as intent, lingnguistic and prompts draft agent to produce better draft)
- RL Agent (Comming Soon)

### Setup 
If you want to use this on your inbox and in your hosted enviorment - welcome it will take 10mins 

Step 1: Head over to google cloud and enable GMAIL API 


