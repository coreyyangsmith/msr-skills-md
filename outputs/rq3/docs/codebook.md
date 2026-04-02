Codebook: Agent Skill Definitions and SDLC Usage

## Instruction Types
How are developers writing skills for their agents?
Form and structure of instructions within a skill file.

### Descriptive (descriptive)
* High level explanations about what the skill does
* Provides context, intent, capabilities without describing exact steps
* Often includes summaries of tools, descriptions of scenarios, overview

Use if and only if the agent skill clearly describes activation scenarios (i.e. "When to use this skill")

Examples
* "Use this skill when..."
* "This skill helps with..."

### Sequential Instructions (instructive)
* Step by step procedures or workflows
* Explicit ordering of actions the agent should follow
* Resembles a checklist, ordered list or algoritm

Examples
* "First..., then..., finally..."
* Numbered or ordered list

### Commands / Execution (commands)
* Direct list of commands (CLI, scripts, fiel edits, API calls)
* Focusing on doing rather than explaining (simialr to instructions)

Examples
* Running scripts
* Modifying files
* Calling APIs

Excludes:
* Basic setup or installation instructions (unless central to the skill)

### Positive Examples (positive-examples)
* Demonstrations of correct or desired behavior
* Shows what a good input/output or usage looks like
* Helps guide the agent through pattern matching

Examples
* "For example"
* "Expected output"

### Negative Examples (negative-examples)
* Illutrations of incorrect usage or undesired behavior
* Often used to constrain or guardrail behavior

Examples
* "Do NOT..."
* "Avoid..."

### References (references)
* Additional documentation or reference information provided
* In Document: clearly structured reference material, describing metrics, APIs, etc in a summarized and clearly formatted table or other structure.
* OR clearly points towards external references, either: (1) website, API, external documentation or (2) other .md files

Examples:
* tables of commands to execute, documentation about APIs etc

---------------------------
## SDLC Stages
<<<<<<< HEAD
### Software Documentation (documentation)
* related to generating or maintaining software documentation (markdowns, readme, code comments, docstrings, etc)
=======
### Software Documentation
#### Agent-Facing
* CLAUDE.md, AGENTS.md, 

#### Regular Software Documentation
* code comments, markdown files, etc

>>>>>>> 2ed4aebf258d69e757bb800eb2d21de6d91327e5

### Software Requirements and Planning (requirements)
* release planning, requirement gathering

### Software Design (software-design)
* Structuring systems, components, or APIs
* High level system decisions, architecture

Examples:
* Designing system architecture
* Designing interfaces or schemas
* Selecting frameworks or patterns


### Code Generation (code-generation)
* Producing or modiyfing source code
* May include some "subcategories", including Core Implementation (writing functions, classes, modules)

#### Third Party Integration (code-integration)
* Third Party Integrations/APIs (interfacing with external services, SDK usage, authentication, API calls)

#### Program Analysis
* Program Analysis (i.e. reverse engineering, project understanding)


### Software Testing (software-testing)
#### Test Generation (test-generation)
(unit tests, integration tests, etc)
#### Code Quality (code-quality)
(Linting, formatting, static analysis, best practices, PRs) (code-quality)
Refactoring
#### Debugging (debugging)

### Software Deployment (devops)
#### SE Workflow Management
* GitHub, creating commit messages, managing git operatioons, etc

#### Deployment
* Release, deployment, maintenance, operations
* , or Configuration/Infrastructure (IaC, YAML, Docker, CI/CD)

### Other
#### Agent Oriented Skills (agent-skill)
* focus on agent behavior rather than SDLC
* includes meta skills or orchestration logic

Examples:
* Multi-agent coordination
* MCP or tool selection logic
* Prompt engineering for agents

#### Outside Scope (outside-scope)
* Wrong programming language
* Marketplace/aggregated skill collection
* Non-development use-case

### Wrong Language (wrong-language) 
* Foreign language or incorrect programming language