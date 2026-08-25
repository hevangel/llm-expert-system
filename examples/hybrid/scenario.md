# Hybrid maintenance scheduling

fact: requires_repair(pump_1)
fact: technician_skill(alice, pump)
fact: available(alice, monday)
fact: maintenance_window(plant_a, monday)

Use forward chaining to identify required work, constraints to assign resources, and planning to order shutdown, repair, verification, and restart.
