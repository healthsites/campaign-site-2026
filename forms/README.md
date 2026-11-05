# Data collection forms

Forms used to collect and validate health facility data during healthsites.io field campaigns.

Form: [CC BY 4.0](LICENSE) · Collected data: [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/) (© OpenStreetMap contributors)

## healthsites-campaign-mobile-data-form.xlsx

An [XLSForm](https://xlsform.org) for recording one health facility per submission. It works in KoboToolbox, ODK Collect and ODK Central.

| | |
|---|---|
| Form ID | `gth_hs_osm` |
| Languages | English, French |
| Output | One record per facility. Each question maps to an [OpenStreetMap tag](https://wiki.openstreetmap.org/wiki/Healthcare), shown in its hint |

### What it collects

- **Identity:** facility name, operator, operator type
- **Location:** GPS point, street address
- **Contact:** phone number (E.164 format), website
- **Status:** operational status, opening hours
- **Services:** facility category, available services, specialist equipment, emergency services, prescription dispensing
- **Capacity:** beds, doctors, nurses
- **Access:** insurance accepted, wheelchair access
- **Utilities:** water source, power source

Three questions are hidden (`relevant = false()`) until they are needed:

- `speciality`: its choice list (`hc_speciality_list`) is a placeholder
- `is_in_health_area` and `is_in_health_zone`: for countries that use these health-system levels, such as the DRC

### Before you deploy

1. **Set `source`.** In the `survey` sheet, change the calculation of `source` to your campaign, for example `"HS-HOT-2026-Uganda"`. Every record carries this value into OpenStreetMap's `source` tag.
2. **Validate.** Upload the file to [XLSForm Online](https://getodk.org/xlsform/), or run `xls2xform healthsites-campaign-mobile-data-form.xlsx form.xml` with [pyxform](https://github.com/XLSForm/pyxform).
3. **Deploy.** In KoboToolbox, create a project, or open an existing one and choose **Replace form**, upload the `.xlsx`, then **Deploy**.

The opening note tells data collectors that what they enter will be published openly under ODbL. Keep it in any adapted version.

### Adapting the form

Changes are welcome. Open an issue or a pull request in this repository.

When you adapt the form for your own campaign:

- Keep the existing question names (the `name` column) unchanged, so your data can be merged back into OpenStreetMap and healthsites.io.
- Add a language with new `label::<Language> (<code>)` and `hint::<Language> (<code>)` columns, for example `label::Portuguese (pt)`.

## Licence

The form is licensed under [Creative Commons Attribution 4.0 International](LICENSE). You may share and adapt it, including for commercial use, if you credit:

> Health facility data form by Open Healthsite Consulting / healthsites.io, licensed under CC BY 4.0.

Data collected with the form is contributed to OpenStreetMap and is licensed under the [Open Database License (ODbL 1.0)](https://opendatacommons.org/licenses/odbl/1-0/).

## Contact

sharehealthdata@healthsites.io · [healthsites.io/contact](https://healthsites.io/contact)
