# Autogen Deep Research (A baseline Deep Research Agent with Autogen Core)

## Development (Setup the requirements for pre-commit)

Setup your environment for development by running:

```
bash scripts/setup.sh
```

## Running Deep Research Agent
1. Create a `.env` file under `/build` folder. Most of the configurations do not have to be touched except for the MODEL_* configs

2. Docker compose up Phoenix for tracing of agents (https://arize.com/docs/phoenix)
```
docker compose -f 'build/docker-compose.phoenix.yml' up -d --build
```

3. Docker compose up the agent stack
```
docker compose -f 'build/docker-compose.yml' up -d --build
```

### Running the Deep Research workflow
The Deep Reseach is mainly run thru the `main.py` script under `agents/src/template_environment` folder.

1. Attach a shell to the `research-agent` container
2. Change the prompt in `agents/src/template_environment/configs/runtime_config.py` to the reseach question you want to ask
3. change directory
```
cd template_environment
```
3. Run `main.py`
```
python main.py
```

**Viewing the research run**
You can view the research run on phoenix by going to `localhost:6006` on your browser

## Roadmap
[] Context/Memory Management

[] Better social network analysis research with Knowledge Graphs

[] Better Reasoning??

## Resources
DEEP RESEARCH AGENTS:
**A SYSTEMATIC EXAMINATION AND ROADMAP** - https://arxiv.org/abs/2506.18096

**RESEARCHRUBRICS: A Benchmark of Prompts and Rubrics For Evaluating Deep Research Agents** - https://www.arxiv.org/abs/2511.07685

**DeepDive: Advancing Deep Search Agents with Knowledge Graphs and Multi-Turn RL** - https://arxiv.org/abs/2509.10446v1