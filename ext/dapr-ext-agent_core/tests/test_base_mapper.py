"""
Copyright 2026 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import unittest

from dapr.ext.agent_core.mapping import BaseAgentMapper


class TestBaseAgentMapper(unittest.TestCase):
    """Tests for BaseAgentMapper shared functionality."""

    def test_extract_provider_openai(self):
        """Test provider extraction for OpenAI modules."""
        self.assertEqual(
            BaseAgentMapper._extract_provider('langchain_openai.chat_models'), 'openai'
        )
        self.assertEqual(BaseAgentMapper._extract_provider('openai.resources'), 'openai')
        self.assertEqual(BaseAgentMapper._extract_provider('strands.models.openai'), 'openai')

    def test_extract_provider_azure_openai(self):
        """Test provider extraction for Azure OpenAI modules."""
        self.assertEqual(
            BaseAgentMapper._extract_provider('langchain_openai.azure'), 'azure_openai'
        )
        self.assertEqual(BaseAgentMapper._extract_provider('azure.openai'), 'azure_openai')
        self.assertEqual(BaseAgentMapper._extract_provider('AZURE_OPENAI'), 'azure_openai')

    def test_extract_provider_anthropic(self):
        """Test provider extraction for Anthropic modules."""
        self.assertEqual(
            BaseAgentMapper._extract_provider('langchain_anthropic.chat_models'), 'anthropic'
        )
        self.assertEqual(BaseAgentMapper._extract_provider('anthropic.client'), 'anthropic')
        self.assertEqual(BaseAgentMapper._extract_provider('strands.models.anthropic'), 'anthropic')

    def test_extract_provider_ollama(self):
        """Test provider extraction for Ollama modules."""
        self.assertEqual(BaseAgentMapper._extract_provider('langchain_ollama'), 'ollama')
        self.assertEqual(BaseAgentMapper._extract_provider('ollama.client'), 'ollama')

    def test_extract_provider_google(self):
        """Test provider extraction for Google/Gemini modules."""
        self.assertEqual(BaseAgentMapper._extract_provider('langchain_google_genai'), 'google')
        self.assertEqual(BaseAgentMapper._extract_provider('google.generativeai'), 'google')
        self.assertEqual(BaseAgentMapper._extract_provider('gemini.client'), 'google')

    def test_extract_provider_cohere(self):
        """Test provider extraction for Cohere modules."""
        self.assertEqual(BaseAgentMapper._extract_provider('langchain_cohere'), 'cohere')
        self.assertEqual(BaseAgentMapper._extract_provider('cohere.client'), 'cohere')

    def test_extract_provider_bedrock(self):
        """Test provider extraction for AWS Bedrock modules."""
        self.assertEqual(BaseAgentMapper._extract_provider('langchain_aws.bedrock'), 'bedrock')
        self.assertEqual(BaseAgentMapper._extract_provider('bedrock.client'), 'bedrock')

    def test_extract_provider_vertexai(self):
        """Test provider extraction for Vertex AI modules."""
        self.assertEqual(BaseAgentMapper._extract_provider('langchain_google_vertexai'), 'vertexai')
        self.assertEqual(BaseAgentMapper._extract_provider('vertexai.client'), 'vertexai')

    def test_extract_provider_unknown(self):
        """Test provider extraction for unknown modules."""
        self.assertEqual(BaseAgentMapper._extract_provider('some.random.module'), 'unknown')
        self.assertEqual(BaseAgentMapper._extract_provider('custom_llm'), 'unknown')
        self.assertEqual(BaseAgentMapper._extract_provider(''), 'unknown')

    def test_extract_provider_case_insensitive(self):
        """Test that provider extraction is case-insensitive."""
        self.assertEqual(BaseAgentMapper._extract_provider('OPENAI.CLIENT'), 'openai')
        self.assertEqual(BaseAgentMapper._extract_provider('Anthropic.Client'), 'anthropic')
        self.assertEqual(BaseAgentMapper._extract_provider('OlLaMa'), 'ollama')

    def test_extract_provider_priority_azure_over_openai(self):
        """Test that Azure OpenAI takes priority when both keywords present."""
        # Azure should be detected before OpenAI
        self.assertEqual(BaseAgentMapper._extract_provider('azure.openai.client'), 'azure_openai')
        self.assertEqual(BaseAgentMapper._extract_provider('openai.azure.wrapper'), 'azure_openai')


if __name__ == '__main__':
    unittest.main()
