# Tests Directory

This directory contains all test files for the multiprocessing datalogger project.

## Test Organization

### Unit Tests
- `test_adc_adapters.py` - ADC adapter pattern tests
- `test_process_supervisor.py` - Process supervision functionality tests
- `test_shared_*.py` - Shared memory buffer tests

### Property-Based Tests
- `test_*_property.py` - Property-based tests using Hypothesis
- These tests validate universal correctness properties across all inputs

### Integration Tests
- `test_api_integration.py` - API endpoint integration tests
- `final_integration_test.py` - Complete system integration test
- `system_validation_test.py` - Comprehensive system validation

### Performance Tests
- `performance_validation_test.py` - Performance benchmarking and validation
- `quick_system_validation.py` - Quick system health check

## Running Tests

### All Tests
```bash
uv run python -m pytest tests/ -v
```

### Property-Based Tests Only
```bash
uv run python -m pytest tests/ -k "property" -v
```

### Integration Tests Only
```bash
uv run python -m pytest tests/ -k "integration" -v
```

### Quick Validation
```bash
uv run python tests/quick_system_validation.py
```

### Full System Validation
```bash
uv run python tests/final_integration_test.py
```

## Test Guidelines

- All test files should be in this `tests/` directory
- Test files should follow the naming convention `test_*.py`
- Integration tests should be named `*integration*.py`
- Validation tests should be named `*validation*.py`
- Property-based tests should be named `*property*.py`

## Note

Test files should never be created in the project root directory. The `.gitignore` file has been updated to prevent this.