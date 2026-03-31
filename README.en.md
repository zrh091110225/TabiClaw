# TabiClaw / Traveling A-Xia

An AI crayfish travel repository that moves one step forward every day.

What you are looking at is not a static project description, but a living travel archive. Every day, A-Xia advances along the route, updates the state, writes a new journal entry, generates an image, and stores all of it in this repository together with the Git history.

## Who Is A-Xia

I am A-Xia, a small crayfish wearing a straw hat, traveling slowly.

I am not just a tool that generates a single piece of copy. Every day I move forward, and I leave behind where I arrived, how much I spent, what I saw, and what I wrote. You can browse my past like a travel scrapbook, or fork my future like a software project.

You can change my prompts, my persona, my route, or the model I use. Or you can simply run the scripts and let me continue the journey.

## What Gets Updated Every Day

- Current city: written to [`data/status.json`](./data/status.json)
- Current travel day: written to [`data/status.json`](./data/status.json) and [`data/journals/index.md`](./data/journals/index.md)
- Current balance: written to [`data/status.json`](./data/status.json) and [`data/journals/index.md`](./data/journals/index.md)
- Daily journal: added under [`data/journals/`](./data/journals/)
- Daily image: added under [`data/images/`](./data/images/)
- Route progress: updated in [`data/route.md`](./data/route.md)
- Journal index and current-status panel: updated in [`data/journals/index.md`](./data/journals/index.md)
- Travel trace: recorded in Git commit history

## What You Can Find In This Repository

- Current status: [`data/status.json`](./data/status.json) and [`data/journals/index.md`](./data/journals/index.md)
- Current route: [`data/route.md`](./data/route.md)
- Journal archive entrypoint: [`data/journals/index.md`](./data/journals/index.md)
- Image directory: [`data/images/`](./data/images/)

**Examples:**
<div style="display: flex; flex-wrap: wrap; gap: 10px;">
  <img src="./data/demo/北京.jpg" width="30%" />
  <img src="./data/demo/成都.jpg" width="30%" />
  <img src="./data/demo/重庆.jpg" width="30%" />
  <img src="./data/demo/大理.jpg" width="30%" />
  <img src="./data/demo/敦煌.jpg" width="30%" />
  <img src="./data/demo/广州.jpg" width="30%" />
  <img src="./data/demo/桂林.jpg" width="30%" />
  <img src="./data/demo/哈尔滨.jpg" width="30%" />
  <img src="./data/demo/湖南.jpg" width="30%" />
  <img src="./data/demo/昆明.jpg" width="30%" />
  <img src="./data/demo/满洲里.jpg" width="30%" />
  <img src="./data/demo/南京.jpg" width="30%" />
  <img src="./data/demo/三亚.jpg" width="30%" />
  <img src="./data/demo/厦门.jpg" width="30%" />
  <img src="./data/demo/上海.jpg" width="30%" />
  <img src="./data/demo/深圳.jpg" width="30%" />
  <img src="./data/demo/苏州.jpg" width="30%" />
</div>

If you want to see where A-Xia is right now, start from [`data/journals/index.md`](./data/journals/index.md). If you want to read through the full journey, start there as well and keep scrolling.

## Why This Is a New Open Source + AI Format

- It is not one-off generated content, but a continuously running travel workflow
- The repository itself is the product: status, journals, images, routes, and commit history are all publicly traceable
- You can either watch A-Xia travel or fork your own version with a different persona and route
- It puts AI generation, script automation, Git history, and content archiving into one playable project

## Quick Start

### Requirements

- Bash 4+
- Python 3
- `jq`
- `bc`
- `curl`
- `bun`

### Installation

```bash
cp .env.example .env
bash scripts/init.sh
```

At minimum, configure these variables in `.env`:

```bash
LLM_PROVIDER=minimax
LLM_API_KEY=your_key
LLM_BASE_URL=https://api.minimax.chat/v1
WRITER_MODEL=MiniMax-Text-01
DASHSCOPE_API_KEY=your_key
```

After running `bash scripts/daily_workflow.sh`, the repository will update:

- [`data/status.json`](./data/status.json)
- [`data/route.md`](./data/route.md)
- A new journal under [`data/journals/`](./data/journals/)
- A new image under [`data/images/`](./data/images/)
- [`data/journals/index.md`](./data/journals/index.md)
- Git commit history

That is also the most direct way to experience this project: run the script once, and A-Xia leaves behind one more day in the repository.

## Common Commands

```bash
# Check configuration and runtime files
bash scripts/init.sh

# Run the full daily workflow
bash scripts/daily_workflow.sh

# Run for a specific date
bash scripts/daily_workflow.sh 2026-03-31

# Replan the full route and reset state to the starting city
bash scripts/replan_route.sh 杭州 北京 --reset

# Continue the route from the current endpoint
bash scripts/continue_route.sh 广州
```

## Documentation Index

- How it works: [`docs/how-it-works.md`](./docs/how-it-works.md)
- Current status: [`data/status.json`](./data/status.json)
- Current route: [`data/route.md`](./data/route.md)
- Travel archive entrypoint: [`data/journals/index.md`](./data/journals/index.md)
- Image directory: [`data/images/`](./data/images/)

## Closing

A-Xia will keep moving forward, and this repository will keep growing new states, journals, images, and commits.

If you want to know where A-Xia is now, open the status files first. If you want to take over its future, fork the repository and change the route, persona, or model so it can keep traveling for you.
