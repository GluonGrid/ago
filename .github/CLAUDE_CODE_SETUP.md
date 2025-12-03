# Claude Code GitHub Actions Setup Guide

This guide explains how to set up and use Claude Code as an automated issue worker for the Ago project.

## Overview

We've configured Claude Code to automatically work on issues labeled with `claude` or when mentioned with `@claude` in comments. Claude will:
- Read the issue description
- Follow our architecture patterns from CLAUDE.md
- Implement the solution
- Create a pull request with the changes

## Setup Instructions

### Prerequisites

1. **Repository Admin Access** - Required to install GitHub App and configure secrets
2. **Anthropic API Key** - Get from https://console.anthropic.com/

### Option 1: Automated Setup (Recommended)

1. **Run the setup command in Claude Code:**
   ```bash
   /install-github-app
   ```

2. **Follow the interactive prompts:**
   - Install the Claude Code GitHub App
   - Configure repository permissions
   - Add ANTHROPIC_API_KEY secret

3. **Verify setup:**
   - Check that `.github/workflows/claude-issue-worker.yml` exists
   - Verify GitHub App installed at https://github.com/apps/claude
   - Confirm secret added in repo settings

### Option 2: Manual Setup

1. **Install GitHub App:**
   - Visit https://github.com/apps/claude
   - Click "Install" and select the `ago` repository
   - Grant permissions:
     - Contents: Read & write
     - Issues: Read & write
     - Pull requests: Read & write

2. **Add API Key Secret:**
   - Go to repository Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `ANTHROPIC_API_KEY`
   - Value: Your Anthropic API key from https://console.anthropic.com/
   - Click "Add secret"

3. **Verify Workflow File:**
   - The workflow file already exists at `.github/workflows/claude-issue-worker.yml`
   - No additional configuration needed

## Usage

### Method 1: Label Issues with 'claude'

1. Create or open an issue
2. Add the `claude` label
3. Claude Code will automatically start working on it
4. Monitor progress in the Actions tab

### Method 2: Mention @claude in Comments

1. Open an issue
2. Comment with `@claude` and optionally add instructions:
   ```
   @claude please implement this feature following the patterns in CLAUDE.md
   ```
3. Claude Code will trigger and start working

### Example Issue Templates

**Feature Request:**
```markdown
## Feature Request: Add Agent Inspection Command

### Description
Add a new CLI command `ago inspect <agent_name>` that shows detailed information about a running agent.

### Requirements
- Show agent configuration (model, tools, temperature)
- Display recent activity and conversation history
- Show current status and resource usage

### Technical Notes
- Add command to `ago/cli/main.py`
- Add daemon handler in `ago/core/daemon.py`
- Use Rich tables for output
- Follow patterns from ONBOARDING.md

Label: claude
```

**Bug Fix:**
```markdown
## Bug: Daemon crashes on empty config file

### Description
When `~/.ago/config.yaml` is empty, the daemon fails to start with a KeyError.

### Steps to Reproduce
1. Delete `~/.ago/config.yaml`
2. Run `ago daemon start`
3. Observe crash

### Expected Behavior
Daemon should create default config if missing or empty.

### Technical Context
- Issue in `ago/core/config.py`
- Need proper error handling and default config creation

Label: claude
```

## What Claude Code Will Do

1. **Read Documentation:**
   - CLAUDE.md for coding standards
   - ONBOARDING.md for architecture
   - Related code files

2. **Implement Solution:**
   - Follow PocketFlow AsyncNode patterns
   - Use proper type hints and docstrings
   - Format with Black and Ruff
   - Add Rich Console output

3. **Create Pull Request:**
   - Clear description of changes
   - Reference to original issue
   - Testing notes

4. **Quality Checks:**
   - Type hints on all functions
   - Proper error handling
   - Async/await correctness
   - No hardcoded paths
   - CLAUDE.md patterns followed

## Configuration

### Workflow File: `.github/workflows/claude-issue-worker.yml`

The workflow is configured with:
- **Trigger:** Issues with `claude` label or `@claude` mentions
- **Permissions:** Write access to contents, PRs, and issues
- **Model:** Claude Sonnet 4.5
- **Max Turns:** 15 (can be adjusted)
- **Context:** Full CLAUDE.md and ONBOARDING.md guidance

### Customizing the Workflow

To adjust Claude's behavior, edit `.github/workflows/claude-issue-worker.yml`:

```yaml
claude_args: "--max-turns 15 --model claude-sonnet-4-5"
```

Options:
- `--max-turns`: Number of reasoning iterations (default: 15)
- `--model`: Claude model to use
  - `claude-sonnet-4-5` (recommended, balanced)
  - `claude-opus-4` (most capable, slower)
  - `claude-haiku-4` (fastest, simpler tasks)

## Monitoring

### View Claude's Work

1. **Actions Tab:**
   - Go to repository → Actions
   - Find "Claude Code Issue Worker" workflows
   - Click on a run to see detailed logs

2. **Issue Comments:**
   - Claude may add status comments to the issue
   - Progress updates appear during execution

3. **Pull Requests:**
   - Claude creates PRs when work is complete
   - Review the PR before merging

### Cost Tracking

- GitHub Actions minutes: Check Settings → Billing
- Anthropic API costs: Check https://console.anthropic.com/
- Optimize by adjusting `--max-turns` for simpler tasks

## Best Practices

### Writing Good Issues for Claude

✅ **DO:**
- Be specific about requirements
- Reference relevant files and patterns
- Include technical context
- Provide examples when helpful
- Use the `claude` label

❌ **DON'T:**
- Be vague or ambiguous
- Skip technical details
- Request massive refactors without breaking down
- Forget to mention architecture constraints

### Example Good Issue

```markdown
## Add Memory Persistence for Agents

### Goal
Save agent conversation history to disk so it persists across restarts.

### Technical Approach
- Store conversations in `~/.ago/conversations/<agent_id>.json`
- Load on agent creation in `ago/core/daemon.py::_create_agent()`
- Save after each message in agent ReAct loop
- Use JSON format with timestamps

### Files to Modify
- `ago/core/daemon.py` - Add load/save logic
- `ago/agents/agent_react_flow.py` - Save after each turn
- `ago/core/config.py` - Add conversations directory path

### Testing
- Create agent, chat, stop daemon, restart, verify history loads

Label: claude
```

## Troubleshooting

### Claude Doesn't Start

**Check:**
1. Issue has `claude` label or comment has `@claude`
2. ANTHROPIC_API_KEY secret is set
3. GitHub App has proper permissions
4. Workflow file exists and is valid

**Solution:**
- Re-run workflow manually from Actions tab
- Check Actions logs for errors
- Verify API key is valid

### Claude Creates Wrong Implementation

**Fix:**
1. Close the PR
2. Add more context to the issue
3. Comment with `@claude` and additional guidance:
   ```
   @claude please redo this following the PocketFlow AsyncNode pattern
   in CLAUDE.md section "Pattern 1: PocketFlow Agent Node"
   ```

### API Rate Limits

**If you hit rate limits:**
1. Reduce `--max-turns` in workflow file
2. Use smaller model (`claude-haiku-4`)
3. Batch multiple issues together
4. Wait and retry later

### Permission Errors

**If Claude can't create PRs:**
1. Verify GitHub App permissions
2. Check repository Settings → Actions → General
3. Ensure "Allow GitHub Actions to create PRs" is enabled

## Security

### API Key Protection

- ✅ ANTHROPIC_API_KEY stored as GitHub Secret (encrypted)
- ✅ Never committed to repository
- ✅ Only accessible to GitHub Actions runners
- ✅ Rotatable without code changes

### Code Review

- ⚠️ **Always review PRs before merging**
- ⚠️ Claude is powerful but not perfect
- ⚠️ Verify security-sensitive changes
- ⚠️ Test locally if making infrastructure changes

### Permissions

The workflow has minimal required permissions:
- `contents: write` - Create branches and commit
- `pull-requests: write` - Create PRs
- `issues: write` - Comment on issues

## Advanced Usage

### Multiple Issues

Claude can work on multiple issues concurrently. Each triggers a separate workflow run.

### Custom Instructions

Add specific instructions in issue comments:
```
@claude implement this but use a different approach:
- Store in SQLite instead of JSON
- Add migration script
- Include comprehensive tests
```

### Retry Failed Attempts

If Claude's first attempt isn't right:
1. Comment on the PR with feedback
2. Close the PR
3. Comment on the original issue: `@claude please try again with this feedback: [your feedback]`

## Resources

- [Claude Code Documentation](https://code.claude.com/docs/en/github-actions)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Anthropic API Console](https://console.anthropic.com/)
- [Ago CLAUDE.md](../CLAUDE.md) - Coding guidelines for Claude
- [Ago ONBOARDING.md](../ONBOARDING.md) - Architecture guide

## Support

If you encounter issues with the Claude Code integration:
1. Check the Actions tab for error logs
2. Review this guide's troubleshooting section
3. Open an issue with the `infrastructure` label
4. Contact repository maintainers

---

**Last Updated:** December 2025
**Maintained By:** Ago Development Team
