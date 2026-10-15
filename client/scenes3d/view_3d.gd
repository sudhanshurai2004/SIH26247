extends Node3D
## Optional Stage 7 3D presentation. It reads playback data and exposes no control interface.

@export_enum("day", "night") var time_of_day := "day"
@export_enum("clear", "haze") var atmosphere := "clear"
@export_enum("rural", "urban") var terrain_style := "rural"
@export var target_fps := 30

@onready var sun: DirectionalLight3D = $Sun
@onready var environment: WorldEnvironment = $WorldEnvironment

func _ready() -> void:
    # This is a target cap for the optional view, not a measured performance claim.
    Engine.max_fps = target_fps
    apply_environment()

func apply_environment() -> void:
    var env := environment.environment
    sun.light_energy = 0.25 if time_of_day == "night" else 1.0
    env.background_color = Color("091426") if time_of_day == "night" else Color("77a9c9")
    env.fog_enabled = atmosphere == "haze"
    env.fog_density = 0.015 if atmosphere == "haze" else 0.0
    $UrbanBlocks.visible = terrain_style == "urban"
    $RuralGround.visible = terrain_style == "rural"
