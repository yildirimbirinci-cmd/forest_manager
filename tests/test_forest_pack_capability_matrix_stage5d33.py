from forest_manager.forest_control.service import ForestProperty, ForestSnapshot, aggregate_capability_matrix
def snap(name):
    return ForestSnapshot(name,4,{"read_only":1,"scalar":2,"color":1},(ForestProperty("a","Float","scalar",True,1.0),ForestProperty("b","BooleanClass","scalar",True,False),ForestProperty("c","Color","color",True,"[0,0,0]"),ForestProperty("d","ArrayParameter","read_only",True,array_metadata={"count":1})),({"name":"d","metadata":{"count":1,"preview_count":1,"element_classes":["Float"],"elements":[{"value_class":"Float","preview":"1.0"}]}},))
def test_matrix():
    m=aggregate_capability_matrix(tuple(snap(f"FM_{i}") for i in range(4)))
    assert m["forest_count"]==4 and m["aggregate_write_mode_counts"]=={"read_only":4,"scalar":8,"color":4}
    assert m["array_element_class_signatures"]["Float"]==4 and m["policy"]["array_parameter"]=="typed_discovery_read_only" and m["verified"] is True
