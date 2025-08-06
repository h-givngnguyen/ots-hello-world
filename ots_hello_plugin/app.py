import os
import pathlib
import threading
import traceback
import importlib.metadata
import yaml

from flask import Blueprint, Flask, jsonify, request, send_from_directory, current_app as app
from flask_security import roles_accepted
from opentakserver.plugins.Plugin import Plugin
from opentakserver.extensions import *

from .default_config import DefaultConfig

class HelloPlugin(Plugin):
    # Use the folder name for URL prefix to avoid hyphen issues
    url_prefix = f"/api/plugins/{pathlib.Path(__file__).resolve().parent.name}"
    blueprint = Blueprint("HelloPlugin", __name__, url_prefix=url_prefix)

    def __init__(self):
        super().__init__()
        self._websocket_wrapper = None
        self._ws_thread = None
        self.load_metadata()

    def activate(self, app: Flask):
        self._app = app
        self._load_config()
        self.load_metadata()

        try:
            logger.info(f"Successfully Loaded {self._name}")
        except BaseException as e:
            logger.error(f"Failed to load {self._name}: {e}")
            logger.error(traceback.format_exc())

    def load_metadata(self):
        try:
            distributions = importlib.metadata.packages_distributions()
            for distro in distributions:
                if str(__name__).startswith(distro):
                    self.name = distributions[distro][0]
                    self.distro = distro
                    info = importlib.metadata.metadata(self.distro)
                    self._metadata = info.json
                    self._metadata['distro'] = distro
                    return self._metadata
        except BaseException as e:
            logger.error(e)

    def _load_config(self):
        for key in dir(DefaultConfig):
            if key.isupper():
                self._config[key] = getattr(DefaultConfig, key)
                self._app.config.update({key: getattr(DefaultConfig, key)})

        with open(os.path.join(self._app.config.get("OTS_DATA_FOLDER"), "config.yml")) as yaml_file:
            yaml_config = yaml.safe_load(yaml_file)
            for key in self._config.keys():
                value = yaml_config.get(key)
                if value:
                    self._config[key] = value
                    self._app.config.update({key: value})

    def stop(self):
        pass

    def get_info(self):
        self.load_metadata()
        self.get_plugin_routes(self.url_prefix)
        return {'name': self.name, 'distro': self.distro, 'routes': self.routes}

    # ------------------ ROUTES ------------------

    @staticmethod
    @roles_accepted("administrator")
    @blueprint.route("/")
    def plugin_info():
        try:
            distributions = importlib.metadata.packages_distributions()
            for distro in distributions:
                if str(__name__).startswith(distro):
                    info = importlib.metadata.metadata(distributions[distro][0])
                    return jsonify(info.json)
            return jsonify({'success': False, 'error': 'Plugin not found'}), 404
        except BaseException as e:
            logger.error(e)
            return jsonify({'success': False, 'error': str(e)}), 500

    @staticmethod
    @roles_accepted("administrator")
    @blueprint.route("/ui")
    def ui():
        plugin_root = pathlib.Path(__file__).parent.resolve()
        return send_from_directory(plugin_root / "ui", "index.html", as_attachment=False)

    @staticmethod
    @roles_accepted("administrator")
    @blueprint.route("/assets/<path:file_name>")
    def serve_asset(file_name):
        plugin_root = pathlib.Path(__file__).parent.resolve()
        assets_path = plugin_root / "ui" / "assets"
        if file_name and (assets_path / file_name).exists():
            return send_from_directory(assets_path, file_name)
        else:
            return '', 404

    @staticmethod
    @roles_accepted("administrator")
    @blueprint.route("/config")
    def config():
        config_data = {}
        for key in dir(DefaultConfig):
            if key.isupper():
                config_data[key] = app.config.get(key)
        return jsonify(config_data)

    @staticmethod
    @roles_accepted("administrator")
    @blueprint.route("/config", methods=["POST"])
    def update_config():
        try:
            result = DefaultConfig.update_config(request.json)
            if result["success"]:
                DefaultConfig.update_config(request.json)
                return jsonify(result)
            else:
                return jsonify(result), 400
        except BaseException as e:
            logger.error("Failed to update config:" + str(e))
            logger.error(traceback.format_exc())
            return jsonify({"success": False, "error": str(e)}), 400

# 👇 Required for OTS to load the plugin!
def load():
    return HelloPlugin.blueprint
