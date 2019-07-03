"""
SPDX-License-Identifier: BSD-3-Clause
Developed by UNH-IOL dpdklab@iol.unh.edu.
"""

from django import forms


class EnvironmentForm(forms.Form):
    # Used to uniquely identify each environment since there are multiple
    # EnvironmentForms in a single view
    environment = forms.IntegerField(widget=forms.HiddenInput())
    # Length based on current model limits
    nic_make = forms.CharField(
        max_length=64,
        help_text='Manufaturer of NIC under test')
    nic_model = forms.CharField(
        max_length=191,
        help_text='Official model name of NIC under test')
    # If None, remove the live_since value
    live_since = forms.DateField(
        required=False,
        help_text='Date since which results should be included in the overall '
                  'result on the dashboard')
    # If None, don't do anything (don't reupload the file and don't remove the file)
    hardware_description = forms.FileField(
        required=False,
        help_text='External hardware description provided by the member. '
                  'This can include setup configuration, topology, and '
                  'general hardware environment information')
