<!-- SPDX-FileCopyrightText: Nova-Violet Role ORG -->
<!-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later -->
<!-- ....................................................................... -->
<!-- RTR-RE Installer Scene Module  ...................................... -->
<!-- file: rtrre-scene.mod
-->

<!-- RTR-RE Installer Scene Module

     Declares the 3D scene vocabulary. The scene is data: an XML
     instance (scene.xml) conforming to this module, rendered by the
     shell's own renderer. The graphics are inferred from the declared
     structure — the scene is a first-class member of the RTR-RE DTD
     family, not hardcoded pixels.

     Conventions:
       - scene: root, carries the theme reference and camera defaults
       - core: the central object (glow, radius, pulse)
       - floor: reflection plane (reflectivity)
       - particles: the memory-stream field (count, spread, speed,
         colors)
       - camera: drift, parallax sensitivity
       - all colors are 3-tuples of 0..1 floats
-->

<!ELEMENT scene (camera, core, floor, particles) >
<!ATTLIST scene
    version CDATA #FIXED "1.0"
    theme (instrument | network | forge) "instrument"
>

<!ELEMENT camera EMPTY >
<!ATTLIST camera
    drift CDATA "0.0012"
    parallax CDATA "0.0004"
    pitch CDATA "-0.16"
    distance CDATA "6.5"
>

<!ELEMENT core EMPTY >
<!ATTLIST core
    radius CDATA "0.55"
    pulse CDATA "0.12"
    glow CDATA "0.5"
    points CDATA "220"
>

<!ELEMENT floor EMPTY >
<!ATTLIST floor
    reflect CDATA "0.35"
    y CDATA "-0.6"
>

<!ELEMENT particles EMPTY >
<!ATTLIST particles
    count CDATA "900"
    spread CDATA "3.2"
    speed CDATA "0.6"
    size-min CDATA "0.6"
    size-max CDATA "2.2"
    color CDATA "0.0,0.9,1.0"
    color2 CDATA "0.12,0.44,1.0"
    color-mix CDATA "0.6"
>
