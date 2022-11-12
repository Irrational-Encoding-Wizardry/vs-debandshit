from __future__ import annotations

from dataclasses import dataclass
from vstools import check_variable, fallback, inject_self, join, normalize_seq, split, vs, CustomIntEnum, KwargsT

from .abstract import Debander

__all__ = [
    'PlaceboDither',
    'Placebo'
]


class PlaceboDither(CustomIntEnum):
    NONE = -1
    """No dithering."""

    BLUE_NOISE = 0
    """
    Dither with blue noise. Very high quality, but requires the use of a
    LUT. Warning: Computing a blue noise texture with a large size can be
    very slow, however this only needs to be performed once. Even so, using
    this with a `lut_size` greater than 6 is generally ill-advised. This is
    the preferred/default dither method.
    """

    DEFAULT = BLUE_NOISE

    ORDERED_LU = 1
    """
    Dither with an ordered (bayer) dither matrix, using a LUT. Low quality,
    and since this also uses a LUT, there's generally no advantage to picking
    this instead of `BLUE_NOISE`. It's mainly there for testing.
    """

    ORDERED_FIXED = 2
    """
    The same as `ORDERED_LUT`, but uses fixed function math instead
    of a LUT. This is faster, but only supports a fixed dither matrix size
    of 16x16 (equal to a `lut_size` of 4). Requires GLSL 130+.
    """

    WHITE_NOISE = 3
    """
    Dither with white noise. This does not require a LUT and is fairly cheap
    to compute. Unlike the other modes it doesn't show any repeating
    patterns either spatially or temporally, but the downside is that this
    is visually fairly jarring due to the presence of low frequencies in the
    noise spectrum. Used as a fallback when the above methods are not
    available.
    """

    @property
    def placebo_args(self) -> KwargsT:
        """Get arguments you must pass to .placebo.Debander for this dither mode."""
        if self is PlaceboDither.NONE:
            return dict(dither=False, dither_algo=0)
        return dict(dither=True, dither_algo=self.value)


@dataclass
class Placebo(Debander):
    radius: float | None = None
    threshold: float | list[float] | None = None
    iterations: int | None = None
    grain: float | list[float] | None = None

    dither: PlaceboDither | None = None
    renderer: bool | None = None

    @inject_self
    def deband(
        self, clip: vs.VideoNode, radius: float = 16.0, threshold: float | list[float] = 4.0,
        iterations: int = 1, grain: float | list[float] = 6.0, dither: PlaceboDither = PlaceboDither.DEFAULT,
        renderer: bool = False
    ) -> vs.VideoNode:
        """
        Main deband function, wrapper for `placebo.Deband <https:/github.com/Lypheo/vs-placebo#vs-placebo>`_

        :param clip:            Source clip
        :param radius:          The debanding filter's initial radius.
                                The radius increases linearly for each iteration.
                                A higher radius will find more gradients,
                                but a lower radius will smooth more aggressively.
        :param threshold:       The debanding filter's cut-off threshold.
                                Higher numbers increase the debanding strength dramatically,
                                but progressively diminish image details.
        :param iterations:      The number of debanding steps to perform per sample.
                                Each step reduces a bit more banding,
                                but takes time to compute.
                                Note that the strength of each step falls off very quickly,
                                so high numbers (>4) are practically useless.
        :param grain:           Add some extra noise to the image.
                                This significantly helps cover up remaining quantization artifacts.
                                Higher numbers add more noise.
                                Note: When debanding HDR sources, even a small amount of grain can result
                                in a very big change to the brightness level.
                                It's recommended to either scale this value down or disable it entirely for HDR.
        :param dither:          Specify what kind of Placebo dithering will be used.
        :param renderer:        Make libplacebo Deband use the renderer API over the normal API.

        :return:                Debanded clip
        """

        assert check_variable(clip, self.__class__.deband)

        radius = fallback(self.radius, radius)
        threshold = normalize_seq(fallback(self.threshold, threshold))
        iterations = fallback(self.iterations, iterations)
        grain = normalize_seq(fallback(self.grain, grain))
        dither = fallback(self.dither, dither)
        renderer = fallback(self.renderer, renderer)

        debs = [
            p.placebo.Deband(1, iterations, thr, radius, gra, **dither.placebo_args, renderer_api=renderer)
            for p, thr, gra in zip(split(clip), threshold, grain)
        ]

        if len(debs) == 1:
            return debs[0]

        return join(debs, clip.format.color_family)