# Contributing to 2Care.ai Voice AI Agent

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing.

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on the work, not the person
- Help others learn and grow

## Getting Started

### 1. Fork & Clone

```bash
git clone https://github.com/yourusername/voice-ai-agent.git
cd voice-ai-agent
```

### 2. Set Up Development Environment

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dev dependencies
pip install -r requirements-dev.txt

# Copy environment template
cp .env.example .env
```

### 3. Start Redis

```bash
docker run -d -p 6379:6379 redis:7-alpine
```

## Development Workflow

### Before Starting

1. Check existing issues and PRs
2. Create an issue for your feature/bug
3. Get approval from maintainers before major changes

### Making Changes

1. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes following the code style

3. Write or update tests:
   ```bash
   pytest tests/ -v
   ```

4. Format and lint code:
   ```bash
   make format  # Black formatting
   make lint    # Pylint check
   ```

### Commit Messages

Follow conventional commits format:

```
type(scope): subject

body (optional)

footer (optional)
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Code style (formatting, missing semicolons)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**
```
feat(agent): add support for voice amplification
fix(stt): handle empty audio chunks gracefully
docs(readme): update installation instructions
test(appointments): add edge case tests for concurrent bookings
```

## Code Style Guidelines

### Python Style

- Line length: 100 characters
- Use type hints for function signatures
- Follow PEP 8
- Use meaningful variable names

**Example:**

```python
from typing import Optional, List
from pydantic import BaseModel

class AppointmentRequest(BaseModel):
    patient_id: str
    doctor_id: str
    preferred_slot: str
    
async def book_appointment(
    request: AppointmentRequest,
    engine: AppointmentEngine
) -> dict[str, Any]:
    """
    Book an appointment with conflict detection.
    
    Args:
        request: Appointment booking details
        engine: Appointment engine instance
        
    Returns:
        Appointment booking result with confirmation ID
        
    Raises:
        ValueError: If slot is already booked
    """
    # Implementation...
```

### Documentation

- Add docstrings to all public functions/classes
- Use triple quotes: `"""`
- Follow Google-style docstrings
- Add examples for complex functions

```python
def check_availability(
    doctor_id: str,
    date: str,
    booked_slots: set[str]
) -> List[str]:
    """
    Get available appointment slots for a doctor.
    
    Args:
        doctor_id: Unique doctor identifier
        date: Date in YYYY-MM-DD format
        booked_slots: Set of already booked times (HH:MM format)
        
    Returns:
        List of available time slots (HH:MM format)
        
    Example:
        >>> slots = check_availability("doc_001", "2026-05-21", {"09:00"})
        >>> print(slots)
        ['09:30', '10:00', '10:30', ...]
    """
```

### Testing

- Write tests for all new features
- Minimum 80% code coverage
- Use descriptive test names
- Test both happy path and edge cases

```python
import pytest

class TestAppointmentBooking:
    @pytest.mark.asyncio
    async def test_book_appointment_success(self):
        """Test successful appointment booking."""
        # Arrange
        engine = AppointmentEngine()
        request = AppointmentRequest(...)
        
        # Act
        result = await engine.book_appointment(request)
        
        # Assert
        assert result["status"] == "confirmed"
        assert result["appointment_id"] is not None
    
    @pytest.mark.asyncio
    async def test_book_conflicting_slot_raises_error(self):
        """Test that booking conflicting slot raises error."""
        engine = AppointmentEngine()
        
        # Book first appointment
        engine.book_appointment(request1)
        
        # Attempt to book same slot
        with pytest.raises(ValueError, match="Slot already booked"):
            engine.book_appointment(request2)
```

## Pull Request Process

### Before Submitting

1. ✅ All tests pass: `pytest -v`
2. ✅ Code is formatted: `make format`
3. ✅ No linting issues: `make lint`
4. ✅ Documentation is updated
5. ✅ CHANGELOG is updated

### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Breaking change

## Related Issues
Closes #(issue number)

## Testing
Describe testing performed

## Checklist
- [ ] Tests pass
- [ ] Code is formatted
- [ ] Documentation updated
- [ ] No breaking changes
```

## Reporting Bugs

### Bug Report Template

**Title:** Brief description of bug

**Description:**
```
### Steps to Reproduce
1. 
2. 
3. 

### Expected Behavior
What should happen

### Actual Behavior
What actually happens

### Environment
- OS: [e.g., Windows 11]
- Python: [e.g., 3.11.0]
- Redis: [e.g., 7-alpine]
- LLM Provider: [e.g., Anthropic]

### Logs
```
Relevant error logs or stack trace
```
```

## Feature Requests

**Title:** Brief description of feature

**Description:**
- **Problem:** What problem does this solve?
- **Solution:** How should it work?
- **Examples:** Use cases and examples

## Performance Guidelines

### Latency Targets

- STT service: < 120ms
- Language detection: < 5ms
- Agent reasoning: < 200ms
- TTS service: < 100ms
- **Total end-to-end: < 450ms**

### When Optimizing

1. Profile first: `python -m py_spy record -o prof.svg uvicorn backend.main:app`
2. Identify bottleneck
3. Implement optimization
4. Measure improvement
5. Ensure no regression

### Database & Caching

- Use Redis connection pooling
- Set appropriate TTLs
- Index frequently queried fields
- Monitor query performance

## Documentation

### Update README if:
- [ ] Adding new feature
- [ ] Changing API endpoint
- [ ] Updating architecture
- [ ] Changing environment variables

### Update DEPLOYMENT.md if:
- [ ] Changing deployment process
- [ ] Adding new infrastructure requirement
- [ ] Updating performance tuning

### Update API docs:
- [ ] FastAPI docstrings automatically generate docs
- [ ] Visit `/docs` and `/redoc` endpoints

## Questions or Need Help?

- **Documentation:** See [QUICKSTART.md](./QUICKSTART.md)
- **Deployment:** See [DEPLOYMENT.md](./DEPLOYMENT.md)
- **Issues:** Create a GitHub issue
- **Discussions:** Use GitHub Discussions

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.

---

Thank you for contributing to 2Care.ai! 🙏
