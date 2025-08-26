# Contributing

Thanks for taking the time to contribute!

## How to propose changes
1. Fork the repo and create a feature branch.
2. Make concise commits with clear messages.
3. Add/update docstrings and README examples if behaviour changes.
4. Open a Pull Request with:
   - What problem it solves.
   - Screenshots/gifs if UI behaviour changes.
   - Any notes on Maya versions/platforms tested.

## Coding style
- Python 3 style, type hints where sensible.
- Keep imports local if they are Maya‑only (to keep linting tools happy).

## Testing
- Launch editor UI and ensure both JSON and live runtime update as expected.
- Try RMB‑hold menu, MMB reordering, and preset switching.
