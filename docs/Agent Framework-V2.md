# Agent Framework

- AI framework to orchestrate custom agents and mcp servers
- goal 1: work efficient and precise on complex task in a so called “stack”
- goal 2: agent subset creation for a “stack” should be generic
- goal 3: create and maintain a knowledge database by working in a “stack”, which is easy-to-read for the AI

# General Notes

---

### Templates

- use templates and schemata for agents etc.
- templates should be reusable blocks (like token efficiency, etc)
- should be linked into the description
- best case scenario (if possible): i change a description file ⇒ will be changed in all corresponding agents via update component (see below)

### Token Efficiency

- use guidelines for token efficiency

### Provider

- should support multiple providers (copilot, claude, etc.)
- setup script asks which provider ⇒ generates either .github/ or .claude/

### Install Script

- does the initial setup:
    - install requirements
    - install mcp servers
    - check everything is up and running
    - ask which provider should be used
    - setup and initialize (with general user/project data) memento
- if needed, create validation scripts

### MCP Servers

Official:

- Git, Github
- Filesystem
- Sequential Thinking
- Memento/Memory
- FastMCP
- Context?
- RAG-MCP?
- MCP Task Queue?
- PostgreSQL/SQLite MCP Server?
- Kubernetes MCP Server?
- Notion

# Phase 1: Stack Creation

---

## Workflow

1. Analyze
    1. Existing Project
        - analyze files
        - find out tech stack
    2. New Project
        - evaluate with user
        - ask questions regarding goal, (tech) preferences
2. Create
    1. create directory
    2. create agents (md files)
    3. create/add mcp servers
    4. create/add skills
    5. init knowledge

## Analyzer Component

### Description

- Analyze either
    - an already existing project directory
    - a project description given by the user
- Create the concept of a - so called - “Stack”:
    - which technologies/programming languages, knowledge is used
    - which agents, mcp servers and skills would be useful to work in this project
- DONT implement

### Contains

- ?

### Execution

- start analyzing when user puts command like “@analyzer analyze /path/to/project” or “@analyzer i want to create a stack for a new project: …”
- already existing project: analyze project structure, read project files, …
- new project: ask questions to find out which tech stack fits the best
- maybe already put knowledge about this into the memento (or in another place?)

## Writer Component

### Description

- use analyzis of the analyzer to IMPLEMENT the stack

### Contains

- ?

### Execution

- create a new directory under “stacks”
- agents which are used in all stacks will be copied to stack directory
- create provider specific directories and agents
- use templates and schemas to create the stack (be STRICT about this!)

# Phase 2: Work in Stack

---

## Workflow (when running an json plan)

- json plan = outcome from planner component, after giving planner component a (complex) task
- step = a json plan consists of “steps”, always a certain task assigned to a certain agent
- plans should also be able to solve in batch-mode: sending the whole plan, AI solves everything together

### Pre-Step

- fetch information from memento
- predict token consumption (adapt step instruction if needed)

### Step

- coordinator orchestrates specialized agents: best matching agent is delegated to solve the task
- specialized agents uses helper services (like mcp services or skills)

### Post-Step

- new (relevant) knowledge is written into memento
- changed logic/behavior is updated in memento

## System Check Component

### Description

- watch agent framework to see if all mcp servers are running and used
- check also other system dependencies (like docker)

### Contains

- MCP server for running system check?

### Execution

- could this be checked while runtime? or does a system check on startup (or after 1 hour runtime)?

## Knowledge Component

### Description

- make sure that knowledge is fetched and updated with every plan-step or smaller single task (dont save unnecessary information to dont blow up the database)
- knowledge MUST be uptodate

### Contains

- knowledge agent
- memento mcp server

### Execution

- pre-step execution: check if any usable information is found in memento
- post-step execution: write/update information in memento

> could be done as skills?
> 

## Planner Component

### Description

- Create a plan (as json schema) to solve a complex task

### Contains

- plan agent (pre-defined)
- research mcp server?

### Execution

- Analyze user’s task description
- do also web research to find already existing solutions for similar tasks
- do internal memento research to find already existing solutions for similar tasks (likely in the same stack)
- ask questions to clarify the goal of the task
- create a json plan (see plan-v2.schema.json)
- json plan does NOT contain linting testing, commiting (will be done by “finalizer”)
- DONT implement

## Worker Component

### Description

- solve json plans

### Contains

- agent-registry mcp server
- plan-execution mcp server
- coordinator agent?
- git agent(s)

### Execution

- Either sequential or batch
- batch:
    - send whole json plan to ai provider in batch mode to have 50% token discount
- sequential:
    - coordinator coordinates the plan (deligates steps to special agents, updates plan)
- creates a new branch with every new plan (ASK if this should be skipped)

## Finalizer Component

### Description

- fix linting
- run tests
- commit changes

### Contains

- git mcp server(s)
- linting, test mcp servers?

### Execution

- will ALWAYS be run after plan was finished
- merge branch after success (ASK)

## Efficiency Component

### Description

- watch and predict big token consumption
- try to avoid by using memento or other
- e.g. instead of reading a huge file, check memento for information

### Contains

- efficiency template
- mcp server?
- skill?

### Execution

- pre-step execution: predict token consumption for actual step
- if huge amount of token, ASK if step execution should be adapted
- make suggestions how to improve token usage before execution a step (only if token consumption is huge)

## Update Component

### Description

- update agents files with

# Todo’s/Questions

- how has the plan to be configured/structured to enable BATCH mode solving?
- which mcp servers are useful for this project?
- what could be solved by skills?
- does it make sense to create an agent alongside a mcp server? e.g. knowledge agent and a knowledge mcp server
- what is better for my usecase? memento ([https://github.com/gannonh/memento-mcp](https://github.com/gannonh/memento-mcp)) or memory ([https://github.com/modelcontextprotocol/servers/tree/main/src/memory](https://github.com/modelcontextprotocol/servers/tree/main/src/memory)) ?