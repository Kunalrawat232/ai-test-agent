# Testing Standards

## Selector Strategy (Priority Order)
1. `data-testid` attributes — preferred, stable across refactors
2. ARIA roles and labels — accessible and meaningful
3. CSS selectors — last resort, keep shallow

## Wait Strategy
- NEVER use `time.sleep()` or hard waits
- Playwright: rely on auto-wait, use `expect()` with timeout
- Selenium: use `WebDriverWait` with explicit conditions

## Test Data
- Use factory functions or fixtures for test data
- Never share state between tests
- Clean up created data in teardown

## Naming Convention
- Test files: `test_<feature>_<framework>.py`
- Test classes: `Test<Feature><Area>`
- Test methods: `test_<action>_<condition>_<expected>`

## CI Requirements
- All tests must pass in headless mode
- Maximum test suite duration: 5 minutes
- Flaky tests must be fixed within 24 hours or quarantined
