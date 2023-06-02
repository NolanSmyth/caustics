from abc import abstractmethod
from typing import Any, Optional
from functools import partial

import torch
from torch import Tensor

from ..constants import arcsec_to_rad, c_Mpc_s
from ..cosmology import Cosmology
from ..parametrized import Parametrized
from .utils import get_magnification

__all__ = ("ThinLens", "ThickLens")

class ThickLens(Parametrized):
    """
    Base class for modeling gravitational lenses that cannot be treated using the thin lens approximation.
    It is an abstract class and should be subclassed for different types of lens models.

    Attributes:
        cosmology (Cosmology): An instance of a Cosmology class that describes the cosmological parameters of the model.
    """

    def __init__(self, name: str, cosmology: Cosmology):
        """
        Initializes a new instance of the ThickLens class.

        Args:
            name (str): The name of the lens model.
            cosmology (Cosmology): An instance of a Cosmology class that describes the cosmological parameters of the model.
        """
        super().__init__(name)
        self.cosmology = cosmology

    @abstractmethod
    def deflection_angle(
        self, x: Tensor, y: Tensor, z_s: Tensor, P: "Packed" = None
    ) -> tuple[Tensor, Tensor]:
        """
        Computes the reduced deflection angle at given coordinates [arcsec].

        Args:
            x (Tensor): Tensor of x coordinates in the lens plane.
            y (Tensor): Tensor of y coordinates in the lens plane.
            z_s (Tensor): Tensor of source redshifts.
            P ("Packed", optional): Additional parameters for the lens model. Defaults to None.

        Returns:
            tuple[Tensor, Tensor]: Tuple of Tensors representing the x and y components of the deflection angle, respectively.
        """
        ...

    def raytrace(
        self, x: Tensor, y: Tensor, z_s: Tensor, P: "Packed" = None
    ) -> tuple[Tensor, Tensor]:
        """
        Performs ray tracing by computing the deflection angle and subtracting it from the initial coordinates.

        Args:
            x (Tensor): Tensor of x coordinates in the lens plane.
            y (Tensor): Tensor of y coordinates in the lens plane.
            z_s (Tensor): Tensor of source redshifts.
            P ("Packed", optional): Additional parameters for the lens model. Defaults to None.

        Returns:
            tuple[Tensor, Tensor]: Tuple of Tensors representing the x and y coordinates of the ray-traced light rays, respectively.
        """
        ax, ay = self.deflection_angle(x, y, z_s, P)
        return x - ax, y - ay

    @abstractmethod
    def Sigma( # TODO Sigma -> surface_density
        self, x: Tensor, y: Tensor, z_s: Tensor, P: "Packed" = None
    ) -> Tensor:
        """
        Computes the projected mass density at given coordinates.

        Args:
            x (Tensor): Tensor of x coordinates in the lens plane.
            y (Tensor): Tensor of y coordinates in the lens plane.
            z_s (Tensor): Tensor of source redshifts.
            P ("Packed", optional): Additional parameters for the lens model. Defaults to None.

        Returns:
            Tensor: The projected mass density at the given coordinates in units of solar masses per square Megaparsec.
        """
        ...

    @abstractmethod
    def time_delay(
        self, x: Tensor, y: Tensor, z_s: Tensor, P: "Packed" = None
    ) -> Tensor:
        """
        Computes the gravitational time delay at given coordinates.

        Args:
            x (Tensor): Tensor of x coordinates in the lens plane.
            y (Tensor): Tensor of y coordinates in the lens plane.
            z_s (Tensor): Tensor ofsource redshifts.
            P ("Packed", optional): Additional parameters for the lens model. Defaults to None.

        Returns:
            Tensor: The gravitational time delay at the given coordinates.
        """
        ...

    def magnification(self, x: Tensor, y: Tensor, z_s: Tensor, P) -> Tensor:
        """
        Computes the gravitational lensing magnification at given coordinates.
    
        Args:
            x (Tensor): Tensor of x coordinates in the lens plane.
            y (Tensor): Tensor of y coordinates in the lens plane.
            z_s (Tensor): Tensor of source redshifts.
            P ("Packed", optional): Additional parameters for the lens model. Defaults to None.
    
        Returns:
            Tensor: The gravitational lensing magnification at the given coordinates.
        """
        return get_magnification(partial(self.raytrace, P = P), x, y, z_s)

class ThinLens(Parametrized):
    """Base class for thin gravitational lenses.

    This class provides an interface for thin gravitational lenses,
    i.e., lenses that can be modeled using the thin lens
    approximation.  The class provides methods to compute several
    lensing quantities such as the deflection angle, convergence,
    potential, surface mass density, and gravitational time delay.

    Args:
        name (str): Name of the lens model.
        cosmology (Cosmology): Cosmology object that encapsulates cosmological parameters and distances.
        z_l (Optional[Tensor], optional): Redshift of the lens. Defaults to None.

    """

    def __init__(self, name: str, cosmology: Cosmology, z_l: Optional[Tensor] = None):
        super().__init__(name)
        self.cosmology = cosmology
        self.add_param("z_l", z_l)

    @abstractmethod
    def deflection_angle( # TODO be explicit about the type of deflection angle used physical or reduce
        self, x: Tensor, y: Tensor, z_s: Tensor, P: "Packed" = None
    ) -> tuple[Tensor, Tensor]:
        """
        Computes the reduced deflection angle of the lens at given coordinates [arcsec].

        Args:
            x (Tensor): Tensor of x coordinates in the lens plane.
            y (Tensor): Tensor of y coordinates in the lens plane.
            z_s (Tensor): Tensor of source redshifts.
            P ("Packed", optional): Additional parameters for the lens model. Defaults to None.

        Returns:
            tuple[Tensor, Tensor]: Reduced deflection angle in x and y directions.
        """
        ...

    def deflection_angle_hat( # TODO: hat -> reduced ? need to double check this
        self, x: Tensor, y: Tensor, z_s: Tensor, P: "Packed" = None
    ) -> tuple[Tensor, Tensor]:
        """
        Computes the physical deflection angle immediately after passing through this lens's plane.

        Args:
            x (Tensor): Tensor of x coordinates in the lens plane.
            y (Tensor): Tensor of y coordinates in the lens plane.
            z_s (Tensor): Tensor of source redshifts.
            P ("Packed", optional): Additional parameters for the lens model. Defaults to None.

        Returns:
            tuple[Tensor, Tensor]: Physical deflection angle in x and y directions in arcseconds.
        """
        z_l = self.unpack(P)[0]

        d_s = self.cosmology.angular_diameter_distance(z_s, P)
        d_ls = self.cosmology.angular_diameter_distance_z1z2(z_l, z_s, P)
        deflection_angle_x, deflection_angle_y = self.deflection_angle(x, y, z_s, P)
        return (d_s / d_ls) * deflection_angle_x, (d_s / d_ls) * deflection_angle_y

    @abstractmethod
    def convergence(
        self, x: Tensor, y: Tensor, z_s: Tensor, P: "Packed" = None
    ) -> Tensor:
        """
        Computes the convergence of the lens at given coordinates.

        Args:
            x (Tensor): Tensor of x coordinates in the lens plane.
            y (Tensor): Tensor of y coordinates in the lens plane.
            z_s (Tensor): Tensor of source redshifts.
            P ("Packed", optional): Additional parameters for the lens model. Defaults to None.

        Returns:
            Tensor: Convergence at the given coordinates.
        """
        ...

    @abstractmethod
    def potential(
        self, x: Tensor, y: Tensor, z_s: Tensor, P: "Packed" = None
    ) -> Tensor:
        """
        Computes the gravitational lensing potential at given coordinates.

        Args:
            x (Tensor): Tensor of x coordinates in the lens plane.
            y (Tensor): Tensor of y coordinates in the lens plane.
            z_s (Tensor): Tensor of source redshifts.
            P ("Packed", optional): Additional parameters for the lens model. Defaults to None.

        Returns: Tensor: Gravitational lensing potential at the given coordinates in arcsec^2.
        """
        ...

    def Sigma(
        self, x: Tensor, y: Tensor, z_s: Tensor, P: "Packed" = None
    ) -> Tensor:
        """
        Computes the surface mass density of the lens at given coordinates.

        Args:
            x (Tensor): Tensor of x coordinates in the lens plane.
            y (Tensor): Tensor of y coordinates in the lens plane.
            z_s (Tensor): Tensor of source redshifts.
            P ("Packed", optional): Additional parameters for the lens model. Defaults to None.

        Returns:
            Tensor: Surface mass density at the given coordinates in solar masses per Mpc^2.
        """
        # Superclass params come before subclass ones
        z_l = self.unpack(P)[0]

        Sigma_cr = self.cosmology.Sigma_cr(z_l, z_s, P)
        return self.convergence(x, y, z_s, P) * Sigma_cr

    def raytrace(
        self, x: Tensor, y: Tensor, z_s: Tensor, P: "Packed" = None
    ) -> tuple[Tensor, Tensor]:
        """
        Perform a ray-tracing operation by subtracting the deflection angles from the input coordinates.

        Args:
            x (Tensor): Tensor of x coordinates in the lens plane.
            y (Tensor): Tensor of y coordinates in the lens plane.
            z_s (Tensor): Tensor of source redshifts.
            P ("Packed", optional): Additional parameters for the lens model. Defaults to None.

        Returns:
            tuple[Tensor, Tensor]: Ray-traced coordinates in the x and y directions.
        """
        ax, ay = self.deflection_angle(x, y, z_s, P) # TODO: use reduced alpha? double check
        return x - ax, y - ay

    def time_delay(
        self, x: Tensor, y: Tensor, z_s: Tensor, P: "Packed" = None
    ):
        """
        Compute the gravitational time delay for light passing through the lens at given coordinates.

        Args:
            x (Tensor): Tensor of x coordinates in the lens plane.
            y (Tensor): Tensor of y coordinates in the lens plane.
            z_s (Tensor): Tensor of source redshifts.
            P ("Packed", optional): Additional parameters for the lens model. Defaults to None.

        Returns:
            Tensor: Time delay at the given coordinates.
        """
        z_l = self.unpack(P)[0]

        d_l = self.cosmology.angular_diameter_distance(z_l, P)
        d_s = self.cosmology.angular_diameter_distance(z_s, P)
        d_ls = self.cosmology.angular_diameter_distance_z1z2(z_l, z_s, P)
        ax, ay = self.deflection_angle(x, y, z_s, P)
        potential = self.potential(x, y, z_s, P)
        factor = (1 + z_l) / c_Mpc_s * d_s * d_l / d_ls
        fp = 0.5 * d_ls**2 / d_s**2 * (ax**2 + ay**2) - potential
        return factor * fp * arcsec_to_rad**2

    def _lensing_jacobian_fft_method(
        self, x: Tensor, y: Tensor, z_s: Tensor, P: "Packed" = None
    ) -> Tensor:
        """
        Compute the lensing Jacobian using the Fast Fourier Transform method.

        Args:
            x (Tensor): Tensor of x coordinates in the lens plane.
            y (Tensor): Tensor of y coordinates in the lens plane.
            z_s (Tensor): Tensor of source redshifts.
            P ("Packed", optional): Additional parameters for the lens model. Defaults to None.

        Returns:
            Tensor: Lensing Jacobian at the given coordinates.
        """
        potential = self.potential(x, y, z_s, P)
        # quick dirty work to get kx and ky. Assumes x and y come from meshgrid... TODO Might want to get k differently
        n = x.shape[-1]
        d = torch.abs(x[0, 0] - x[0, 1])
        k = torch.fft.fftfreq(2 * n, d=d)
        kx, ky = torch.meshgrid([k, k], indexing="xy")
        # Now we compute second derivatives in Fourier space, then inverse Fourier transform and unpad
        pad = 2 * n
        potential_tilde = torch.fft.fft(potential, (pad, pad))
        potential_xx = torch.abs(torch.fft.ifft2(-(kx**2) * potential_tilde))[..., :n, :n]
        potential_yy = torch.abs(torch.fft.ifft2(-(ky**2) * potential_tilde))[..., :n, :n]
        potential_xy = torch.abs(torch.fft.ifft2(-kx * ky * potential_tilde))[..., :n, :n]
        j1 = torch.stack(
            [1 - potential_xx, -potential_xy], dim=-1
        )  # Equation 2.33 from Meneghetti lensing lectures
        j2 = torch.stack([-potential_xy, 1 - potential_yy], dim=-1)
        jacobian = torch.stack([j1, j2], dim=-1)
        return jacobian

    def magnification(self, x: Tensor, y: Tensor, z_s: Tensor, P: "Packed") -> Tensor:
        """
        Compute the gravitational magnification at the given coordinates.

        Args:
            x (Tensor): Tensor of x coordinates in the lens plane.
            y (Tensor): Tensor of y coordinates in the lens plane.
            z_s (Tensor): Tensor of source redshifts.
            P ("Packed", optional): Additional parameters for the lens model. Defaults to None.

        Returns:
            Tensor: Gravitational magnification at the given coordinates.
        """
        return get_magnification(partial(self.raytrace, P = P), x, y, z_s)
