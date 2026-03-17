# Contributing

This project is open to improvements and contributions. If you have ideas or find bugs, here is how to help.

## 🐛 Reporting Bugs

If you find a problem:

1. **Check it has not already been reported** — search [Issues](../../issues)

2. **Open a new Issue** with:
   - A descriptive title
   - Steps to reproduce
   - Expected vs. actual behaviour
   - Your environment (OS, Python version, etc.)

## 💡 Proposing Improvements

Ideas for the project:

- New leagues or markets
- Statistical model improvements
- Integration with real-odds APIs
- Web dashboard for historical results
- Backtesting framework

## 🔧 Local Development

### Set up the environment

```bash
git clone https://github.com/your-username/soccer_picks.git
cd soccer_picks

python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### Make changes

```bash
# Create a branch for your feature
git checkout -b feature/my-improvement

# Make changes ...

# Run tests
python tests/test_calendar.py
python tests/test_formatter.py
python tests/test_bot.py

# Commit
git add .
git commit -m "Short description of the change"

# Push
git push origin feature/my-improvement
```

### Open a Pull Request

1. Go to GitHub and open a Pull Request from your branch
2. Describe the changes and the motivation
3. Wait for feedback
4. Merge once approved

## 📝 Style Guidelines

### Python
- All code and comments in **English**
- Type hints on public functions
- Descriptive docstrings (Args / Returns / Raises)
- PEP 8 style guide

### Commits
```
Short title (50 chars max)

More detailed description if needed.
- Point 1
- Point 2
```

## 🧪 Before Opening a PR

- ✓ All tests pass
- ✓ No obvious errors or regressions
- ✓ `requirements.txt` updated if new packages were added
- ✓ `README.md` updated if configuration changed

## 📖 Documentation

If you change something significant, update:
- `README.md`
- Relevant setup / automation guides
- Docstrings in the affected code

## ✅ Welcome PRs

- ✅ Bug fixes
- ✅ Performance improvements
- ✅ New statistical models
- ✅ New data-source integrations
- ✅ Documentation improvements
- ✅ Tests

## ❌ Please Avoid

- ❌ Large, undiscussed changes (open an Issue first)
- ❌ Duplicated code
- ❌ Unnecessary dependencies
- ❌ Hard-coded paths (use `pathlib`)
- ❌ Committing `.env` (use `.env.example` instead)

## 🎯 Contribution Roadmap

Popular areas where help is wanted:

1. **Real odds integration** — Betfair / Bet365 API
2. **Dashboard** — Web UI for historical picks and accuracy
3. **Backtesting** — Framework for validating model accuracy
4. **Advanced ML** — Neural networks, gradient boosting
5. **More markets** — Corners, cards, Asian handicap, etc.

## 📞 Contact

If you have questions:
- Open a Discussion on GitHub
- Review the documentation
- Search existing Issues

---

Thank you for contributing to Soccer Picks! ⚽
