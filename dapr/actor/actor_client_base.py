# -*- coding: utf-8 -*-
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from abc import ABC, abstractmethod

class DaprActorStateTransaction(object):
    def __init__(self, operation, key, value):
        self.operation = operation
        self.key = key
        self.value = value

class DaprActorReminder(object):
    def __init__(self, due_time, period, data):
        self.due_time = due_time
        self.period = period
        self.data = data

class DaprActorTimer(object):
    def __init__(self, due_time, period, data, callback):
        self.due_time = due_time
        self.period = period
        self.data = data
        self.callback = callback

class DaprActorClientBase(ABC):
    @abstractmethod
    def invoke_method(self, actor_type, actor_id, method, data) -> object: ...

    @abstractmethod
    def save_state(self, actor_type, actor_id, key, data) -> None: ...
    
    @abstractmethod
    def save_state_transactional(self, actor_type, actor_id, states) -> None: ...
    
    @abstractmethod
    def get_state(self, actor_type, actor_id, key) -> object: ...
    
    @abstractmethod
    def delete_state(self, actor_type, actor_id, key) -> None: ...
    
    @abstractmethod
    def create_reminder(self, actor_type, actor_id, name, reminder_data) -> None: ...

    @abstractmethod
    def get_reminder(self, actor_type, actor_id, name) -> DaprActorReminder: ...
    
    @abstractmethod
    def delete_reminder(self, actor_type, actor_id, name) -> None: ...

    @abstractmethod
    def create_timer(self, actor_type, actor_id, name, timer_data) -> None: ...
    
    @abstractmethod
    def delete_timer(self, actor_type, actor_id, name) -> None: ...
