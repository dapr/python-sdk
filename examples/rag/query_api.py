# -*- coding: utf-8 -*-
# Copyright 2026 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""The Azure-native flagship query path: hybrid retrieval + a grounded, cited answer.

    Azure AI Search hybrid (vector + keyword) retrieval, through the stable alias
        -> Azure OpenAI chat completion, grounded in the retrieved chunks
        -> an answer with citations back to the source blobs, or a plain
           "not enough evidence" result when retrieval didn't surface enough.

Requires RAG_VECTOR_STORE=azure-ai-search and RAG_EMBEDDER=azure-openai (see
.env.example), plus AZURE_OPENAI_CHAT_DEPLOYMENT for the answer-generation
deployment (which may differ from the embeddings deployment).

    dapr run --app-id rag-query --resources-path components/ -- python3 query_api.py "What is the remote work policy?"
"""

from __future__ import annotations

import argparse
import json
import os

from config import build_retrieval_resolver, optional_env, require_env

from dapr.ext.rag import AzureOpenAIChatClient


def build_chat_client() -> AzureOpenAIChatClient:
    return AzureOpenAIChatClient(
        endpoint=require_env('AZURE_OPENAI_ENDPOINT'),
        deployment=require_env('AZURE_OPENAI_CHAT_DEPLOYMENT'),
        api_key=optional_env('AZURE_OPENAI_API_KEY'),
    )


def answer(question: str, *, top_k: int = 5) -> dict:
    resolver = build_retrieval_resolver()
    try:
        index_version = resolver.resolve_active_version()
        if index_version is None:
            return {
                'answer': 'No index has been activated yet for this pipeline.',
                'citations': [],
                'index_version': None,
                'workflow_instance_id': None,
            }
        matches = resolver.query(question, top_k=top_k)
    finally:
        resolver.close()

    chat = build_chat_client()
    result = chat.generate_answer(question, matches, index_version=index_version)
    return result.to_dict()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('question')
    parser.add_argument('--top-k', type=int, default=int(os.environ.get('RAG_QUERY_TOP_K', '5')))
    args = parser.parse_args()

    result = answer(args.question, top_k=args.top_k)
    print(json.dumps(result, indent=2, default=str))


if __name__ == '__main__':
    main()
