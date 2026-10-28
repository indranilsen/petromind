"""Capability sets shared by tool schemas and the Python executor."""
BASE_TOOLS = frozenset({"list_sensors", "get_sensor_history", "submit_diagnosis"})
VARIANT_TOOLS = {
    "sensor_only": BASE_TOOLS,
    "topology": BASE_TOOLS | {"get_equipment_neighbors"},
    "graphrag": BASE_TOOLS | {"get_equipment_neighbors", "search_similar_incidents"},
}
METHODS = ("sensor_only", "topology", "graphrag", "fixed", "adaptive")
