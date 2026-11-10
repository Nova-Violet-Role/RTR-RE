<!-- ....................................................................... -->
<!-- RTR-RE Installer UI Module  ....................................... -->
<!-- file: rtrre-installer-ui.mod
-->

<!-- RTR-RE Installer UI Module

     Declares the shell vocabulary: screens, preset cards, components,
     cockpit panels, plan rows, progress stream, log lines, and the
     easter egg. The shell markup in index.html conforms to this module.

     Conventions (XHTML family):
       - element names are lowercase, hyphenated
       - every non-empty element carries a content model
       - attributes are declared in ATTLIST with defaulted values where
         sensible
       - the data stream (span-like content) is CDATA, never parsed
-->

<!-- ============ Document shell ============ -->

<!ELEMENT html (head, body) >
<!ATTLIST html
    xmlns CDATA #FIXED "http://www.w3.org/1999/xhtml"
    data-theme (instrument | network | forge) "instrument"
>

<!ELEMENT head (meta, title, link*) >
<!ELEMENT title (#PCDATA) >
<!ELEMENT meta EMPTY >
<!ATTLIST meta
    charset CDATA #IMPLIED
    name CDATA #IMPLIED
    content CDATA #IMPLIED
>
<!ELEMENT link EMPTY >
<!ATTLIST link
    rel CDATA #IMPLIED
    href CDATA #IMPLIED
>

<!ELEMENT body (canvas, header, main, script*) >
<!ATTLIST body
    data-theme (instrument | network | forge) "instrument"
>

<!ELEMENT canvas EMPTY >
<!ATTLIST canvas
    id ID #REQUIRED
>

<!-- ============ HUD ============ -->

<!ELEMENT header (div, div) >
<!ELEMENT div (#PCDATA | button | c-name | c-desc)* >
<!ATTLIST div
    id ID #IMPLIED
    class CDATA #IMPLIED
>
<!ELEMENT button (#PCDATA) >
<!ATTLIST button
    id ID #IMPLIED
    class CDATA #IMPLIED
    data-preset CDATA #IMPLIED
    data-nav CDATA #IMPLIED
    type CDATA #IMPLIED
    title CDATA #IMPLIED
>

<!-- ============ Screens ============ -->

<!ELEMENT main (section+) >
<!ELEMENT section (h1 | h2 | h3 | p | div | button | select | input | span)* >
<!ATTLIST section
    id ID #REQUIRED
    class CDATA #IMPLIED
>

<!ELEMENT h1 (#PCDATA) >
<!ELEMENT h2 (#PCDATA) >
<!ELEMENT h3 (#PCDATA) >
<!ELEMENT p (#PCDATA) >
<!ELEMENT span (#PCDATA) >
<!ATTLIST span
    id ID #IMPLIED
    class CDATA #IMPLIED
>

<!ELEMENT select (#PCDATA | option)* >
<!ATTLIST select
    id ID #IMPLIED
>
<!ELEMENT option (#PCDATA) >
<!ATTLIST option
    value CDATA #IMPLIED
    selected CDATA #IMPLIED
>
<!ELEMENT input EMPTY >
<!ATTLIST input
    id ID #IMPLIED
    type CDATA #IMPLIED
    min CDATA #IMPLIED
    max CDATA #IMPLIED
    step CDATA #IMPLIED
    value CDATA #IMPLIED
>

<!-- ============ Preset selection ============ -->

<!ELEMENT preset-grid (preset-card+) >
<!ELEMENT preset-card (preset-name, preset-desc, preset-value) >
<!ATTLIST preset-card
    data-preset CDATA #REQUIRED
>
<!ELEMENT preset-name (#PCDATA) >
<!ELEMENT preset-desc (#PCDATA) >
<!ELEMENT preset-value (#PCDATA) >

<!-- ============ Custom component selection ============ -->

<!ELEMENT component-grid (component*) >
<!ELEMENT component (span, div) >
<!ATTLIST component
    data-id CDATA #REQUIRED
    class CDATA #IMPLIED
>
<!ELEMENT c-name (#PCDATA) >
<!ELEMENT c-desc (#PCDATA) >

<!-- ============ Cockpit (hardcore) ============ -->

<!ELEMENT cockpit (panel+) >
<!ELEMENT panel (h3, input?, select?, readout?, recommend?, tip?) >
<!ELEMENT readout (#PCDATA) >
<!ELEMENT recommend (#PCDATA) >
<!ELEMENT tip (#PCDATA) >

<!-- ============ Plan / progress ============ -->

<!ELEMENT plan (plan-item*) >
<!ELEMENT plan-item (k, v) >
<!ELEMENT k (#PCDATA) >
<!ELEMENT v (#PCDATA) >

<!ELEMENT stream-track (stream-fill) >
<!ELEMENT stream-fill EMPTY >
<!ATTLIST stream-fill
    id ID #IMPLIED
    class CDATA #IMPLIED
>

<!ELEMENT log (line*) >
<!ELEMENT line (#PCDATA) >
<!ATTLIST line
    class CDATA #IMPLIED
>

<!-- ============ Completion / easter egg ============ -->

<!ELEMENT easter-card (button) >
<!ELEMENT easter-reveal (h3, citation) >
<!ATTLIST easter-reveal
    hidden CDATA #IMPLIED
>
<!ELEMENT citation (#PCDATA) >
<!ATTLIST citation
    id ID #IMPLIED
>

<!-- The data stream: span content is verbatim CDATA — never parsed,
     never expanded. This is the LAW.AMP.13 discipline applied to the
     installer itself.
-->
