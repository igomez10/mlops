Zsh completion for `ebay-cli`

1. Refresh the generated completion file:

```bash
make completion-zsh
```

2. Add the repo completion directory to `fpath` in `~/.zshrc`:

```zsh
fpath=(/Users/ignacio/mlops/scripts/completion $fpath)
autoload -U compinit
compinit
```

3. Reload your shell:

```bash
source ~/.zshrc
```

Notes:
- The completion file is generated for the installed entry point `ebay-cli`.
- Completion is attached to `ebay-cli`, not to `uv run ebay-cli` or `uv run python -m pkg.ebay_cli`.
- Use the direct command after activating the virtualenv, or put `.venv/bin` on your `PATH`:

```bash
source /Users/ignacio/mlops/.venv/bin/activate
ebay-cli <TAB>
```

- If the wrapper is missing, run `uv sync` first so the console script is installed in `.venv`.
