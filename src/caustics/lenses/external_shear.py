from typing import Optional, Union, Annotated, Callable
from functools import wraps

from torch import Tensor
import torch

from .base import ThinLens, CosmologyType, NameType, ZLType
from ..parametrized import unpack
from ..packed import Packed

__all__ = "ExternalShear"


def convert_params(method: Callable):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        if hasattr(self, "_convert_params"):
            kwargs = self._convert_params(*args, **kwargs)
        return method(self, *args, **kwargs)

    return wrapper


class ExternalShear(ThinLens):
    _null_params = {
        "gamma_1": 0.01,
        "gamma_2": 0.0,
    }
    """
    Represents an external shear effect in a gravitational lensing system.

    Attributes
    ----------
    name: str
        Identifier for the lens instance.

    cosmology: Cosmology
        The cosmological model used for lensing calculations.

    z_l: Optional[Union[Tensor, float]]
        The redshift of the lens.

        *Unit: unitless*

    gamma_1, gamma_2: Optional[Union[Tensor, float]]
        Shear components (cartesian parametrization).

        *Unit: unitless*
        
    gamma: Optional[Union[Tensor, float]]
        Shear magnitude (polar parametrization).

        *Unit: unitless*

    phi: Optional[Union[Tensor, float]]
        Shear angle (polar parametrization).

        *Unit: radians*

    Notes
    ------
    The shear components gamma_1 and gamma_2 represent an external shear, a gravitational
    distortion that can be caused by nearby structures outside of the main lens galaxy.
    """
    def __init__(
        self,
        cosmology: CosmologyType,
        z_l: ZLType = None,
        gamma_1: Annotated[
            Optional[Union[Tensor, float]],
            "Shear component in the vertical direction",
            True,
        ] = None,
        gamma_2: Annotated[
            Optional[Union[Tensor, float]],
            "Shear component in the y=-x direction",
            True,
        ] = None,
        gamma: Annotated[
            Optional[Union[Tensor, float]], "Shear magnitude", True
        ] = None,
        phi: Annotated[Optional[Union[Tensor, float]], "Shear angle", True] = None,
        parametrization: Annotated[
            str, "Parametrization of the shear field", {"cartesian", "polar"}
        ] = "cartesian",
        s: Annotated[
            float, "Softening length for the elliptical power-law profile"
        ] = 0.0,
        name: NameType = None,
    ):
        super().__init__(cosmology, z_l, name=name)
        if parametrization.lower() == "cartesian":
            self.add_param("gamma_1", gamma_1)
            self.add_param("gamma_2", gamma_2)
        elif parametrization.lower() == "polar":
            self.add_param("gamma", gamma)
            self.add_param("phi", phi)
        else:
            raise ValueError(
                f"parametrization must be either 'cartesian' or 'polar', got {parametrization}"
            )
        self.s = s
        if parametrization.lower() == "cartesian":
            self._convert_params = lambda self, *args, **kwargs: kwargs  # do nothing
        elif parametrization.lower() == "polar":
            self._convert_params = (
                self._convert_polar_to_cartesian
            )  # convert polar parameters to cartesian

    def _convert_polar_to_cartesian(self, *args, **kwargs):
        gamma = kwargs.get("gamma")
        phi = kwargs.get("phi")
        # This breaks if gamma or phi are not provided (or are None)
        gamma_1, gamma_2 = self._polar_to_cartesian(gamma, phi)
        kwargs["gamma_1"] = gamma_1
        kwargs["gamma_2"] = gamma_2
        return kwargs

    @staticmethod
    def _polar_to_cartesian(gamma: Tensor, phi: Tensor) -> tuple[Tensor, Tensor]:
        gamma_1 = gamma * torch.cos(2 * phi)
        gamma_2 = gamma * torch.sin(2 * phi)
        return gamma_1, gamma_2

    @staticmethod
    def _cartesian_to_polar(gamma_1: Tensor, gamma_2: Tensor) -> tuple[Tensor, Tensor]:
        gamma = torch.sqrt(gamma_1**2 + gamma_2**2)
        phi = 0.5 * torch.atan2(gamma_2, gamma_1)
        return gamma, phi

    @unpack
    @convert_params
    def potential(
        self,
        x: Tensor,
        y: Tensor,
        z_s: Tensor,
        *args,
        params: Optional["Packed"] = None,
        z_l: Optional[Tensor] = None,
        gamma_1: Optional[Tensor] = None,
        gamma_2: Optional[Tensor] = None,
        gamma: Optional[Tensor] = None,
        phi: Optional[Tensor] = None,
        **kwargs,
    ) -> Tensor:
        """
        Calculates the lensing potential.

        Parameters
        ----------
        x: Tensor
            x-coordinates in the lens plane.

            *Unit: arcsec*

        y: Tensor
            y-coordinates in the lens plane.

            *Unit: arcsec*

        z_s: Tensor
            Redshifts of the sources.

            *Unit: unitless*

        params: (Packed, optional)
            Dynamic parameter container.

        Returns
        -------
        Tensor
            The lensing potential.

            *Unit: arcsec^2*

        """
        # Equation 5.127 of Meneghetti et al. 2019
        return 0.5 * gamma_1 * (x**2 - y**2) + gamma_2 * x * y

    @unpack
    @convert_params
    def reduced_deflection_angle(
        self,
        x: Tensor,
        y: Tensor,
        z_s: Tensor,
        *args,
        params: Optional["Packed"] = None,
        z_l: Optional[Tensor] = None,
        gamma_1: Optional[Tensor] = None,
        gamma_2: Optional[Tensor] = None,
        gamma: Optional[Tensor] = None,
        phi: Optional[Tensor] = None,
        **kwargs,
    ) -> tuple[Tensor, Tensor]:
        """
        Calculates the reduced deflection angle.

        Parameters
        ----------
        x: Tensor
            x-coordinates in the lens plane.

            *Unit: arcsec*

        y: Tensor
            y-coordinates in the lens plane.

            *Unit: arcsec*

        z_s: Tensor
            Redshifts of the sources.

            *Unit: unitless*

        params: (Packed, optional)
            Dynamic parameter container.

        Returns
        -------
        x_component: Tensor
            Deflection Angle in x-direction.

            *Unit: arcsec*

        y_component: Tensor
            Deflection Angle in y-direction.

            *Unit: arcsec*

        """
        # Derivative of the potential
        a1 = x * gamma_1 + y * gamma_2
        a2 = x * gamma_2 - y * gamma_1
        return a1, a2

    @unpack
    @convert_params
    def convergence(
        self,
        x: Tensor,
        y: Tensor,
        z_s: Tensor,
        *args,
        params: Optional["Packed"] = None,
        z_l: Optional[Tensor] = None,
        gamma_1: Optional[Tensor] = None,
        gamma_2: Optional[Tensor] = None,
        gamma: Optional[Tensor] = None,
        phi: Optional[Tensor] = None,
        **kwargs,
    ) -> Tensor:
               """
        The convergence is zero by definition for an external shear.

        Parameters
        ----------
        x: Tensor
            x-coordinates in the lens plane.

            *Unit: arcsec*

        y: Tensor
            y-coordinates in the lens plane.

            *Unit: arcsec*

        z_s: Tensor
            Redshifts of the sources.

            *Unit: unitless*

        params: (Packed, optional)
            Dynamic parameter container.

        Returns
        -------
        Tensor
            Convergence for an external shear.

            *Unit: unitless*

        """
        return torch.zeros_like(x)
