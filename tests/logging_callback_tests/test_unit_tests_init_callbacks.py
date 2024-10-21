import json
import os
import sys
from datetime import datetime
from unittest.mock import AsyncMock

from pydantic.main import Model

sys.path.insert(
    0, os.path.abspath("../..")
)  # Adds the parent directory to the system-path

from typing import Literal

import pytest
import litellm
import asyncio
import logging
from litellm._logging import verbose_logger

from litellm.integrations.lago import LagoLogger
from litellm.integrations.openmeter import OpenMeterLogger
from litellm.integrations.braintrust_logging import BraintrustLogger
from litellm.integrations.galileo import GalileoObserve
from litellm.integrations.langsmith import LangsmithLogger
from litellm.integrations.literal_ai import LiteralAILogger
from litellm.integrations.prometheus import PrometheusLogger
from litellm.integrations.datadog.datadog import DataDogLogger
from litellm.integrations.gcs_bucket.gcs_bucket import GCSBucketLogger
from litellm.integrations.opik.opik import OpikLogger
from litellm.integrations.opentelemetry import OpenTelemetry
from litellm.integrations.argilla import ArgillaLogger
from litellm.proxy.hooks.dynamic_rate_limiter import _PROXY_DynamicRateLimitHandler


callback_class_str_to_classType = {
    "lago": LagoLogger,
    "openmeter": OpenMeterLogger,
    "braintrust": BraintrustLogger,
    "galileo": GalileoObserve,
    "langsmith": LangsmithLogger,
    "literalai": LiteralAILogger,
    "prometheus": PrometheusLogger,
    "datadog": DataDogLogger,
    "gcs_bucket": GCSBucketLogger,
    "opik": OpikLogger,
    "argilla": ArgillaLogger,
    "opentelemetry": OpenTelemetry,
    # OTEL compatible loggers
    "logfire": OpenTelemetry,
    "arize": OpenTelemetry,
    "langtrace": OpenTelemetry,
}

expected_env_vars = {
    "LAGO_API_KEY": "api_key",
    "LAGO_API_BASE": "mock_base",
    "LAGO_API_EVENT_CODE": "mock_event_code",
    "OPENMETER_API_KEY": "openmeter_api_key",
    "BRAINTRUST_API_KEY": "braintrust_api_key",
    "GALILEO_API_KEY": "galileo_api_key",
    "LITERAL_API_KEY": "literal_api_key",
    "DD_API_KEY": "datadog_api_key",
    "DD_SITE": "datadog_site",
    "GOOGLE_APPLICATION_CREDENTIALS": "gcs_credentials",
    "OPIK_API_KEY": "opik_api_key",
    "LANGTRACE_API_KEY": "langtrace_api_key",
}


def reset_all_callbacks():
    litellm.callbacks = []
    litellm.input_callback = []
    litellm.success_callback = []
    litellm.failure_callback = []
    litellm._async_success_callback = []
    litellm._async_failure_callback = []


initial_env_vars = {}


def init_env_vars():
    for env_var, value in expected_env_vars.items():
        if env_var not in os.environ:
            os.environ[env_var] = value
        else:
            initial_env_vars[env_var] = os.environ[env_var]


def reset_env_vars():
    for env_var, value in initial_env_vars.items():
        os.environ[env_var] = value


all_callback_required_env_vars = []


async def use_callback_in_llm_call(
    callback: str, used_in: Literal["callbacks", "success_callback"]
):
    if callback == "dynamic_rate_limiter":
        # internal CustomLogger class that expects internal_usage_cache passed to it, it always fails when tested in this way
        return
    elif callback == "argilla":
        litellm.argilla_transformation_object = {}

    if used_in == "callbacks":
        litellm.callbacks = [callback]
    elif used_in == "success_callback":
        litellm.success_callback = [callback]

    for _ in range(1):
        await litellm.acompletion(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.1,
            mock_response="hello",
        )

        await asyncio.sleep(0.5)

        expected_class = callback_class_str_to_classType[callback]

        assert isinstance(litellm._async_success_callback[0], expected_class)
        assert isinstance(litellm._async_failure_callback[0], expected_class)
        assert isinstance(litellm.success_callback[0], expected_class)
        assert isinstance(litellm.failure_callback[0], expected_class)

        assert len(litellm._async_success_callback) == 1
        assert len(litellm._async_failure_callback) == 1
        assert len(litellm.success_callback) == 1
        assert len(litellm.failure_callback) == 1
        assert len(litellm.callbacks) == 1


@pytest.mark.asyncio
async def test_init_custom_logger_compatible_class_as_callback():
    init_env_vars()

    for callback in litellm._known_custom_logger_compatible_callbacks:
        print(f"Testing callback: {callback}")
        reset_all_callbacks()

        await use_callback_in_llm_call(callback, used_in="callbacks")

    reset_env_vars()
