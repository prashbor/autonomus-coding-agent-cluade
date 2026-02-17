"""Testing models for comprehensive test results and reporting."""

from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field


class TestResult(BaseModel):
    """Individual test result."""

    test_name: str = Field(description="Name/description of the test")
    status: Literal["pass", "fail", "skip"] = Field(description="Test execution status")
    duration: float = Field(description="Test execution time in seconds")
    error_message: Optional[str] = Field(default=None, description="Error message if test failed")
    file_path: Optional[str] = Field(default=None, description="Path to test file")


class TestSuite(BaseModel):
    """Collection of related tests with summary statistics."""

    name: str = Field(description="Name of the test suite")
    type: Literal["unit", "integration", "e2e", "stress", "failure"] = Field(
        description="Type of test suite"
    )
    total_tests: int = Field(description="Total number of tests in suite")
    passed: int = Field(description="Number of tests that passed")
    failed: int = Field(description="Number of tests that failed")
    skipped: int = Field(description="Number of tests that were skipped")
    duration: float = Field(description="Total execution time for suite in seconds")
    results: List[TestResult] = Field(default_factory=list, description="Individual test results")

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_tests == 0:
            return 0.0
        return (self.passed / self.total_tests) * 100

    @property
    def all_passed(self) -> bool:
        """Check if all tests in suite passed."""
        return self.failed == 0 and self.total_tests > 0


class ComprehensiveTestReport(BaseModel):
    """Complete test report covering all test types."""

    project_name: str = Field(description="Name of the project being tested")
    timestamp: datetime = Field(default_factory=datetime.now, description="When tests were executed")

    # Individual feature tests (from normal development)
    individual_tests: List[TestSuite] = Field(
        default_factory=list,
        description="Test suites for individual features"
    )

    # Comprehensive test suites
    integration_tests: Optional[TestSuite] = Field(
        default=None,
        description="Tests for how features work together"
    )
    e2e_tests: Optional[TestSuite] = Field(
        default=None,
        description="End-to-end user workflow tests"
    )
    stress_tests: Optional[TestSuite] = Field(
        default=None,
        description="Performance and load tests"
    )
    failure_tests: Optional[TestSuite] = Field(
        default=None,
        description="Failure scenario and error handling tests"
    )

    @property
    def all_tests_pass(self) -> bool:
        """Check if all tests across all suites passed."""
        test_suites = [
            *self.individual_tests,
            self.integration_tests,
            self.e2e_tests,
            self.stress_tests,
            self.failure_tests
        ]

        # Filter out None suites and check if all passed
        valid_suites = [suite for suite in test_suites if suite is not None]
        return all(suite.all_passed for suite in valid_suites)

    @property
    def total_tests(self) -> int:
        """Total number of tests across all suites."""
        total = sum(suite.total_tests for suite in self.individual_tests)

        if self.integration_tests:
            total += self.integration_tests.total_tests
        if self.e2e_tests:
            total += self.e2e_tests.total_tests
        if self.stress_tests:
            total += self.stress_tests.total_tests
        if self.failure_tests:
            total += self.failure_tests.total_tests

        return total

    @property
    def total_passed(self) -> int:
        """Total number of passed tests across all suites."""
        total = sum(suite.passed for suite in self.individual_tests)

        if self.integration_tests:
            total += self.integration_tests.passed
        if self.e2e_tests:
            total += self.e2e_tests.passed
        if self.stress_tests:
            total += self.stress_tests.passed
        if self.failure_tests:
            total += self.failure_tests.passed

        return total

    @property
    def confidence_level(self) -> Literal["high", "medium", "low"]:
        """Determine confidence level based on test results."""
        if not self.all_tests_pass:
            return "low"

        # High confidence if we have comprehensive tests
        has_comprehensive = any([
            self.integration_tests,
            self.e2e_tests,
            self.stress_tests,
            self.failure_tests
        ])

        if has_comprehensive and self.total_tests >= 10:
            return "high"
        elif self.total_tests >= 5:
            return "medium"
        else:
            return "low"