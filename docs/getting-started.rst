Getting Started
===============

Installation
------------

Install the plugin from the QGIS plugin repository
or download the zip from the repository releases.

From Release ZIP
^^^^^^^^^^^^^^^^

1. Download the latest release ZIP from the
   `GitHub releases <https://github.com/Joonalai/macro-qgis-plugin/releases>`_
2. In QGIS, go to **Plugins** > **Manage and Install Plugins...**
3. Select **Install from ZIP** and choose the downloaded file


Usage
-----

Once installed, the macro panel is available in the QGIS Development Tools panel.
Open QGIS Development Tools and interact with the Macro tab.

.. image:: macro.gif
   :alt: Macro demonstration

Recording a Macro
^^^^^^^^^^^^^^^^^

Click the **Record** button in the macro panel, then interact with QGIS normally
(click, type, navigate, etc.). The macro records your mouse and keyboard events.
Stop recording to save the macro.

Playing Back a Macro
^^^^^^^^^^^^^^^^^^^^

Select a saved macro and click the **Play** button to replay the recorded events.

Building Macro Workflows
^^^^^^^^^^^^^^^^^^^^^^^^

A macro workflow plays existing macros one after another, and the same macro
can be used several times. On the **Macro workflows** tab, create a workflow
and add macros to it by dragging them from the **All macros** tab or with the
add menus. Drag the steps or use the arrow buttons to reorder them, and click
**Play** to run the workflow. The step that is playing is marked in the tree.

Saving and Loading Macros
^^^^^^^^^^^^^^^^^^^^^^^^^

Click the **Save** button to save all macros and macro workflows to a file.
To share a single workflow, use **Export workflow** on the **Macro workflows**
tab. It saves the workflow with the macros it uses. Selected macros can be
exported from the context menu of the **All macros** tab.

Use the **Open** button to load macros and workflows from a file. Macros and
workflows that are already in the panel are not loaded again.
