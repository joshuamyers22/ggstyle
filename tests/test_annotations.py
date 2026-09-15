import matplotlib.pyplot as plt

from ggstyle._annotations import Annotation, draw


def test_draw_applies_defaults_without_mutating_requested_style() -> None:
    _, ax = plt.subplots()
    annotation = Annotation("vline", (2.0,), "event", {"color": "red"})
    draw(ax, annotation, float)

    assert annotation.kwargs == {"color": "red"}
    assert len(annotation.artists) == 2
    assert annotation.artists[0].get_color() == "red"
    plt.close(ax.figure)
