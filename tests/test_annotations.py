import matplotlib.pyplot as plt

from ggstyle._annotations import Annotation, draw, replay


def test_draw_applies_defaults_without_mutating_requested_style() -> None:
    _, ax = plt.subplots()
    annotation = Annotation("vline", (2.0,), "event", {"color": "red"})
    draw(ax, annotation, float)

    assert annotation.kwargs == {"color": "red"}
    assert len(annotation.artists) == 2
    assert annotation.artists[0].get_color() == "red"
    plt.close(ax.figure)


def test_replay_replaces_artists_using_the_new_coordinate_mapping() -> None:
    _, ax = plt.subplots()
    annotation = Annotation("span", (1.0, 3.0), None, {})
    draw(ax, annotation, float)
    original = annotation.artists[0]

    replay(ax, [annotation], lambda value: float(value) * 2)

    replacement = annotation.artists[0]
    assert replacement is not original
    assert original not in ax.patches
    assert replacement.get_x() == 2.0
    assert replacement.get_width() == 4.0
    plt.close(ax.figure)
