from flask import current_app, _app_ctx_stack, jsonify, request, abort
from dapr.actor import ActorRuntime

class DaprActor(object):

    actor_runtime = ActorRuntime

    def __init__(
        self,
        app=None,
        actor_idle_timeout="1h",
        actor_scan_interval="30s",
        drain_ongoing_call_timeout="60s",
        drain_rebalanced_actors=True
    ):
        self.app = app

        self._actor_config = {
            'actorIdleTimeout': actor_idle_timeout,
            'actorScanInterval': actor_scan_interval,
            'drainOngoingCallTimeout': drain_ongoing_call_timeout,
            'drainRebalancedActors': drain_rebalanced_actors
        }

        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        registered_actors = self.actor_runtime.registered_actor_types
        app.config.setdefault('actor_entities', registered_actors)
    
        self._add_actor_config_route(app)
        self._add_actor_activation_route(app)
        self._add_actor_deactivation_route(app)
        self._add_actor_method_route(app)
        self._add_actor_reminder_route(app)
        self._add_actor_timer_route(app)

    def teardown(self, exception):
        # TODO: Deactivate all actors
        pass

    def _get_entities_from_ctx(self):
        ctx = _app_ctx_stack.top
        return ctx.actor_entities if hasattr(ctx, 'actor_entities') else []
    
    def _add_actor_config_route(self, app):
        registered_actors = self._get_entities_from_ctx()
        if len(registered_actors) > 0:
            def handler():
                self._actor_config['entities'] = registered_actors
                return self._actor_config
            app.add_url_rule('/dapr/config', None, handler, methods=['GET'])
    
    def _add_actor_activation_route(self, app):
        def handler(actor_type_name, actor_id):
            self.actor_runtime.activate(actor_type_name, actor_id)
            return jsonify({'message': '{}.{} actor is activated'.format(actor_type_name, actor_id)}), 200
        app.add_url_rule('/actors/<actor_type_name>/<actor_id>', None, handler, methods=['POST'])
    
    def _add_actor_deactivation_route(self, app):
        def handler(actor_type_name, actor_id):
            self.actor_runtime.activate(actor_type_name, actor_id)
            return jsonify({'message': '{}.{} actor is deactivated'.format(actor_type_name, actor_id)}), 200
        app.add_url_rule('/actors/<actor_type_name>/<actor_id>', None, handler, methods=['DELETE'])
    
    def _add_actor_method_route(self, app):
        def handler(actor_type_name, actor_id, method_name):
            self.actor_runtime.dispatch(actor_type_name, actor_id, method_name, request.json)
            # TODO: serialize the result properly
            return jsonify({'message': '{} method in {}.{} actor is called'.format(method_name, actor_type_name, actor_id)}), 200
        app.add_url_rule('/actors/<actor_type_name>/<actor_id>/method/<method_name>', None, handler, methods=['PUT'])

    def _add_actor_reminder_route(self, app):
        def handler(actor_type_name, actor_id, reminder_name):
            self.actor_runtime.fire_reminder(actor_type_name, actor_id, reminder_name, request.json)
            return jsonify({'message': '{} reminder in {}.{} actor is called'.format(reminder_name, actor_type_name, actor_id)}), 200
        app.add_url_rule('/actors/<actor_type_name>/<actor_id>/method/remind/<reminder_name>', None, handler, methods=['PUT'])

    def _add_actor_timer_route(self, app):
        def handler(actor_type_name, actor_id, timer_name):
            self.actor_runtime.fire_timer(actor_type_name, actor_id, timer_name)
            return jsonify({'message': '{} timer in {}.{} actor is called'.format(timer_name, actor_type_name, actor_id)}), 200
        app.add_url_rule('/actors/<actor_type_name>/<actor_id>/method/timer/<timer_name>', None, handler, methods=['PUT'])