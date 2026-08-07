"""The hop-ring layout exists twice and the two copies must not drift.

``gnn.sage_explainer.display_hop_ring_layout`` writes ``x``/``y`` into the
published community, and ``recoveryHopRingLayout`` in the recovery explainer UI
recomputes the same placement in the browser so artifacts published before the
producer emitted hop-ring coordinates still read structurally.  If they diverge,
a case looks different depending on which artifact vintage produced it, which is
exactly the confusion the layout was introduced to remove.
"""

import importlib.util
import json
import math
import subprocess
from pathlib import Path

import pytest

from gnn.sage_explainer import DISPLAY_LAYOUT_RADIUS, display_hop_ring_layout

UI_PATH = (
    Path(__file__).resolve().parents[1]
    / "Documents/Data/scripts/v9_recovery_explainer_ui.py"
)
UI_SPEC = importlib.util.spec_from_file_location("v9_recovery_explainer_ui", UI_PATH)
UI = importlib.util.module_from_spec(UI_SPEC)
UI_SPEC.loader.exec_module(UI)

TARGET = "p000"


def _community(hop1_count, hop2_per, cross_edges=0, orphans=0):
    """A community with cross-links and orphans, not just a clean tree."""
    nodes = [{"node_id": TARGET, "message_distance": 0, "target": True}]
    edges = []
    hop1 = []
    for index in range(hop1_count):
        node_id = f"a{index:03d}"
        hop1.append(node_id)
        nodes.append({"node_id": node_id, "message_distance": 1, "target": False})
        edges.append({"u": TARGET, "v": node_id, "edge_id": f"e_t_{node_id}"})
    hop2 = []
    for parent in hop1:
        for index in range(hop2_per):
            node_id = f"b{parent}_{index:03d}"
            hop2.append(node_id)
            nodes.append({"node_id": node_id, "message_distance": 2, "target": False})
            edges.append({"u": parent, "v": node_id, "edge_id": f"e_{parent}_{node_id}"})
    # Extra parents make "lowest-id parent wins" observable rather than vacuous.
    for index in range(cross_edges):
        edges.append(
            {
                "u": hop1[(index * 7 + 3) % len(hop1)],
                "v": hop2[index % len(hop2)],
                "edge_id": f"x_{index:03d}",
            }
        )
    for index in range(orphans):
        nodes.append({"node_id": f"z{index:03d}", "message_distance": 2, "target": False})
    return nodes, edges


def _js_layout(nodes, edges):
    script = UI.V9_RECOVERY_EXPLAINER_JS + (
        "\nconst layout=recoveryHopRingLayout("
        + json.dumps(nodes)
        + ","
        + json.dumps(edges)
        + ");"
        "\nconst out={};"
        "\nif(layout){for(const entry of layout){out[entry[0]]=[entry[1].x,entry[1].y];}}"
        "\nconsole.log(JSON.stringify({ok:Boolean(layout),positions:out}));"
    )
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )
    return json.loads(completed.stdout)


CASES = {
    "tree": (8, 6, 0, 0),
    "cross_links": (8, 6, 20, 0),
    "orphans": (6, 5, 9, 4),
    "at_display_ceiling": (32, 15, 60, 0),
    "single_ring": (12, 0, 0, 0),
}


@pytest.mark.parametrize("case", sorted(CASES))
def test_python_and_javascript_layouts_agree(case):
    nodes, edges = _community(*CASES[case])
    expected = display_hop_ring_layout(nodes, edges, TARGET)
    actual = _js_layout(nodes, edges)

    assert actual["ok"] is True
    assert set(actual["positions"]) == set(expected)
    for node_id, (x, y) in expected.items():
        js_x, js_y = actual["positions"][node_id]
        assert js_x == pytest.approx(x, abs=1e-12), node_id
        assert js_y == pytest.approx(y, abs=1e-12), node_id


def test_layout_places_the_target_at_the_centre_and_hops_on_rings():
    nodes, edges = _community(8, 6)
    layout = display_hop_ring_layout(nodes, edges, TARGET)

    assert layout[TARGET] == (0.5, 0.5)

    def radius(node_id):
        x, y = layout[node_id]
        return math.hypot(x - 0.5, y - 0.5)

    hop1 = {round(radius(n["node_id"]), 9) for n in nodes if n["message_distance"] == 1}
    hop2 = {round(radius(n["node_id"]), 9) for n in nodes if n["message_distance"] == 2}
    assert len(hop1) == 1 and len(hop2) == 1
    assert 0 < hop1.pop() < hop2.pop() <= DISPLAY_LAYOUT_RADIUS


def test_layout_coordinates_stay_inside_the_unit_square():
    # The UI rejects a community whose coordinates are not finite unit values.
    nodes, edges = _community(32, 15, 60)
    layout = display_hop_ring_layout(nodes, edges, TARGET)

    assert len(layout) == len(nodes)
    for node_id, (x, y) in layout.items():
        assert math.isfinite(x) and math.isfinite(y), node_id
        assert 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0, node_id


def test_layout_is_deterministic_and_order_independent():
    nodes, edges = _community(8, 6, 20)
    baseline = display_hop_ring_layout(nodes, edges, TARGET)

    assert display_hop_ring_layout(nodes, edges, TARGET) == baseline
    assert (
        display_hop_ring_layout(list(reversed(nodes)), list(reversed(edges)), TARGET)
        == baseline
    )


def test_a_crowded_ring_is_split_into_concentric_bands():
    from gnn.sage_explainer import (
        DISPLAY_RING_BAND_CAPACITY,
        MAX_DISPLAY_RING_BANDS,
    )

    # 32 hop-1 nodes stay on one radius; 480 hop-2 nodes exceed the band
    # capacity and must spread rather than pile onto a single circle.
    nodes, edges = _community(32, 15, 60)
    layout = display_hop_ring_layout(nodes, edges, TARGET)

    def radii(distance):
        return {
            round(
                math.hypot(
                    layout[node["node_id"]][0] - 0.5,
                    layout[node["node_id"]][1] - 0.5,
                ),
                9,
            )
            for node in nodes
            if node["message_distance"] == distance
        }

    hop1 = radii(1)
    hop2 = radii(2)
    assert len(hop1) == 1, "32 nodes fit within one band"
    assert len(hop2) == MAX_DISPLAY_RING_BANDS
    assert 480 > DISPLAY_RING_BAND_CAPACITY
    # Bands stay outside the inner ring and inside the overall radius.
    assert min(hop2) > max(hop1)
    assert max(hop2) <= DISPLAY_LAYOUT_RADIUS


def test_no_two_nodes_share_a_position():
    nodes, edges = _community(32, 15, 60)
    layout = display_hop_ring_layout(nodes, edges, TARGET)

    assert len(set(layout.values())) == len(layout)


def test_children_are_drawn_in_a_contiguous_arc_under_their_parent():
    hop1_count, hop2_per = 8, 6
    nodes, edges = _community(hop1_count, hop2_per)
    layout = display_hop_ring_layout(nodes, edges, TARGET)

    def angle(node_id):
        x, y = layout[node_id]
        return math.atan2(y - 0.5, x - 0.5) % (2 * math.pi)

    ring_size = hop1_count * hop2_per
    for index in range(hop1_count):
        parent = f"a{index:03d}"
        angles = sorted(angle(f"b{parent}_{j:03d}") for j in range(hop2_per))
        spread = angles[-1] - angles[0]
        # A contiguous block of hop2_per slots spans (hop2_per - 1) steps.
        assert spread <= 2 * math.pi * (hop2_per - 1) / ring_size + 1e-9, parent


def test_degenerate_inputs_do_not_raise():
    assert display_hop_ring_layout([], [], TARGET) == {}

    solo = [{"node_id": TARGET, "message_distance": 0, "target": True}]
    assert display_hop_ring_layout(solo, [], TARGET) == {TARGET: (0.5, 0.5)}

    # A node with no neighbour one ring in is still placed.
    orphan = solo + [{"node_id": "z", "message_distance": 2, "target": False}]
    placed = display_hop_ring_layout(orphan, [], TARGET)
    assert set(placed) == {TARGET, "z"}

    # A non-target node at distance 0 must not collide with the centre.
    collision = solo + [{"node_id": "q", "message_distance": 0, "target": False}]
    assert display_hop_ring_layout(collision, [], TARGET)["q"] != (0.5, 0.5)


def test_javascript_layout_declines_without_message_distance():
    # Falling back to payload coordinates is correct here; inventing rings from
    # a missing hop count would misrepresent the graph.
    nodes = [
        {"node_id": TARGET, "target": True, "x": 0.1, "y": 0.2},
        {"node_id": "a000", "target": False, "x": 0.3, "y": 0.4},
    ]
    assert _js_layout(nodes, [])["ok"] is False


def _explanation(*, with_hops=True, max_nodes=None, max_edges=None):
    """Minimal explanation that satisfies buildCommunityDrawCommands."""
    people = [TARGET, "a000", "a001", "b000"]
    hops = {TARGET: 0, "a000": 1, "a001": 1, "b000": 2}
    nodes = []
    for index, person in enumerate(people):
        node = {
            "node_id": person,
            # Deliberately wrong-looking payload coordinates: when the hop-ring
            # layout runs it must override them, and when it declines it must
            # fall back to exactly these.
            "x": 0.1 * (index + 1),
            "y": 0.9,
            "target": person == TARGET,
            "pooled_member": True,
            "caught_before_snapshot": person == "a001",
        }
        if with_hops:
            node["message_distance"] = hops[person]
        nodes.append(node)
    edges = [
        {
            "edge_id": "edge-1",
            "u": TARGET,
            "v": "a000",
            "edge_type": "COTRAVEL",
            "explainer_median": 0.8,
            "message_hop": 1,
        },
        {
            "edge_id": "edge-2",
            "u": TARGET,
            "v": "a001",
            "edge_type": "RESIDENCE",
            "explainer_median": 0.2,
            "message_hop": 1,
        },
        {
            "edge_id": "edge-3",
            "u": "a000",
            "v": "b000",
            "edge_type": "SHARED_PLATE",
            "explainer_median": 0.5,
            "message_hop": 2,
        },
    ]
    community = {
        "complete": True,
        "nodes": nodes,
        "edges": edges,
        "provenance_expansions": [],
    }
    if max_nodes is not None:
        community["projection_policy"] = {
            "max_nodes": max_nodes,
            "max_edges": max_edges,
        }
    node_ids = [node["node_id"] for node in nodes]
    edge_ids = [edge["edge_id"] for edge in edges]
    return {
        "person_id": TARGET,
        "community": community,
        "flow_stages": [
            {
                "stage_id": stage_id,
                "node_ids": node_ids,
                "edge_ids": edge_ids,
                "emphasized_edge_ids": ["edge-1"] if stage_id == "first_hop" else [],
            }
            for stage_id in (
                "first_hop",
                "second_hop",
                "component_pool",
                "rank_fusion",
            )
        ],
    }


def _draw(explanation, **overrides):
    options = {
        "mode": "flow",
        "stageId": "first_hop",
        "selectedFactorId": None,
        "query": "",
    }
    options.update(overrides)
    script = UI.V9_RECOVERY_EXPLAINER_JS + (
        "\nconst result=buildCommunityDrawCommands("
        + json.dumps(explanation)
        + ","
        + json.dumps(options)
        + ");"
        # Maps do not survive JSON.stringify, so unwrap them explicitly.
        "\nconst adjacency={};"
        "\nif(result.adjacency){for(const entry of result.adjacency)"
        "{adjacency[entry[0]]=Array.from(entry[1]).sort();}}"
        "\nconst hopCounts={};"
        "\nif(result.stats){for(const entry of result.stats.hopCounts)"
        "{hopCounts[entry[0]]=entry[1];}}"
        "\nconsole.log(JSON.stringify({"
        "available:result.available,reason:result.reason,"
        "nodes:result.nodes,tableNodes:result.tableNodes,"
        "layoutSource:result.layoutSource,"
        "stats:result.stats?Object.assign({},result.stats,{hopCounts}):null,"
        "adjacency}));"
    )
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )
    return json.loads(completed.stdout)


# ``nodes``/``edges`` are the stage-filtered canvas slice, which was introduced
# after this file was written and is bounded for canvas performance. Layout is a
# property of the whole projection, so these read ``tableNodes`` — the complete
# projection every node is positioned in — rather than whatever the selected
# stage happens to draw.
def test_draw_commands_place_nodes_with_the_hop_ring_layout():
    result = _draw(_explanation())

    assert result["available"] is True
    assert result["layoutSource"] == "hop_rings"
    positions = {node["id"]: (node["x"], node["y"]) for node in result["tableNodes"]}
    assert positions[TARGET] == (0.5, 0.5)
    # The payload put every node at y=0.9; the ring layout must have replaced it.
    assert all(y != 0.9 for _, y in positions.values())
    assert {node["id"]: node["hop"] for node in result["tableNodes"]} == {
        TARGET: 0,
        "a000": 1,
        "a001": 1,
        "b000": 2,
    }
    # Whatever the stage draws is positioned by the same layout.
    drawn = {node["id"]: (node["x"], node["y"]) for node in result["nodes"]}
    assert drawn and all(positions[node_id] == point for node_id, point in drawn.items())


def test_draw_commands_fall_back_to_payload_coordinates_without_hops():
    result = _draw(_explanation(with_hops=False))

    assert result["available"] is True
    assert result["layoutSource"] == "payload"
    positions = {node["id"]: (node["x"], node["y"]) for node in result["tableNodes"]}
    assert positions[TARGET] == (0.1, 0.9)
    assert positions["b000"] == pytest.approx((0.4, 0.9))
    assert all(node["hop"] is None for node in result["tableNodes"])


def test_layout_is_scoped_to_the_drawn_projection_not_the_whole_community():
    """Ring radii come from the projection's deepest hop, so laying out over the
    whole community would squeeze every drawn node into the innermost sliver of
    a ring sized for members that are never drawn.  The chunked schema-3 sidecar
    hands the UI all 35k community members while only ~600 reach the canvas.
    """
    from gnn.sage_explainer import DISPLAY_LAYOUT_RADIUS, MAX_DISPLAY_RING_BANDS

    # 1600 hop-1 members overflow the 1500-node display bound, and the hop-3
    # members sort last so they are the ones the projection drops.
    nodes = [{"node_id": "p000", "message_distance": 0, "x": 0.5, "y": 0.5}]
    edges = []
    for index in range(1600):
        node_id = f"a{index:05d}"
        nodes.append({"node_id": node_id, "message_distance": 1, "x": 0.5, "y": 0.5})
        edges.append(
            {
                "edge_id": f"e{index:05d}",
                "u": "p000",
                "v": node_id,
                "edge_type": "COTRAVEL",
                "message_hop": 1,
                "explainer_median": 0.0,
            }
        )
    for index in range(5):
        nodes.append(
            {"node_id": f"z{index:03d}", "message_distance": 3, "x": 0.5, "y": 0.5}
        )
    explanation = {
        "person_id": "p000",
        "community": {
            "complete": True,
            "nodes": nodes,
            "edges": edges,
            "provenance_expansions": [],
        },
        "flow_stages": [
            {"stage_id": "first_hop", "edge_rule": {"max_message_hop": 1}},
            {"stage_id": "second_hop", "edge_rule": {"max_message_hop": 2}},
            {
                "stage_id": "component_pool",
                "edge_rule": {"edge_type": "COTRAVEL", "both_pooled_members": True},
            },
            {"stage_id": "rank_fusion", "edge_rule": {"match_none": True}},
        ],
    }

    result = _draw(explanation)
    assert result["available"] is True, result.get("reason")
    assert result["layoutSource"] == "hop_rings"

    drawn = {
        node["id"]: (node["x"], node["y"])
        for node in result["nodes"]
        if node["id"] != "p000"
    }
    radii = {round(math.hypot(x - 0.5, y - 0.5), 9) for x, y in drawn.values()}
    # Every drawn member is hop 1, so the projection's deepest ring is 1. Laying
    # out over the whole community would size the rings for its hop-3 members
    # and pull ring 1 more than halfway back towards the centre.
    scoped = DISPLAY_LAYOUT_RADIUS * 1 / (1 + 0.5)
    whole_community = DISPLAY_LAYOUT_RADIUS * 1 / (3 + 0.5)
    # 1499 members overflow the band capacity, so hop 1 spreads over its
    # concentric bands; the innermost band sits at the scoped ring radius.
    assert len(radii) == MAX_DISPLAY_RING_BANDS
    assert min(radii) == pytest.approx(scoped, abs=1e-9)
    assert max(radii) <= DISPLAY_LAYOUT_RADIUS
    assert scoped > whole_community
    # The dropped hop-3 members never reach the canvas.
    assert not any(node_id.startswith("z") for node_id in drawn)
    # Rows outside the display bound are not laid out and keep payload x/y, so
    # the complete data table still renders them.
    undrawn = [
        node for node in result["tableNodes"] if node["id"].startswith("z")
    ]
    assert len(undrawn) == 5
    assert all((node["x"], node["y"]) == (0.5, 0.5) for node in undrawn)


def test_draw_commands_report_counts_for_the_density_readout():
    result = _draw(_explanation())
    stats = result["stats"]

    assert stats["nodeCount"] == 4
    assert stats["edgeCount"] == 3
    assert stats["hopCounts"] == {"0": 1, "1": 2, "2": 1}
    assert stats["emphasizedEdgeCount"] == 1


def test_draw_commands_flag_a_community_clipped_by_the_display_bound():
    unclipped = _draw(_explanation(max_nodes=512, max_edges=1024))
    assert unclipped["stats"]["clipped"] is False
    assert unclipped["stats"]["maxNodes"] == 512

    # Four nodes against a bound of four means the projection filled its cap and
    # the real community may be larger than what is drawn.
    clipped = _draw(_explanation(max_nodes=4, max_edges=1024))
    assert clipped["stats"]["clipped"] is True


def test_draw_commands_expose_neighbourhoods_for_click_to_focus():
    result = _draw(_explanation())

    # Each node is inside its own neighbourhood so focusing never hides it.
    assert result["adjacency"][TARGET] == sorted([TARGET, "a000", "a001"])
    assert result["adjacency"]["b000"] == sorted(["a000", "b000"])
    assert result["adjacency"]["a001"] == sorted([TARGET, "a001"])
