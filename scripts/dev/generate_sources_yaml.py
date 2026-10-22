import yaml
from pathlib import Path

sources_dict = {
  'sources': {
    'us_ofac': {
      'id': 'us_ofac',
      'authority': 'US Department of the Treasury (OFAC)',
      'landing_page': 'https://ofac.treasury.gov/specially-designated-nationals-and-blocked-persons-list-sdn-human-readable-lists',
      'candidate_urls': [
        'https://www.treasury.gov/ofac/downloads/sdn.csv',
        'https://sanctionssearch.ofac.treas.gov/Files/sdn.csv'
      ],
      'allowed_domains': ['treasury.gov', 'ofac.treasury.gov', 'sanctionssearch.ofac.treas.gov'],
      'discovery': r'href=[\"\'](https?://[^\"\']*/sdn\.csv)[\"\']',
      'expected': {
        'format': 'csv',
        'min_bytes': 8000000,
        'required_columns': ['ent_num', 'SDN_Name', 'SDN_Type', 'Program'],
        'min_records': 15000,
        'count_range_ratio': [0.70, 1.50]
      },
      'max_age_days': 7,
      'closure_keywords': ['no longer being updated', 'no longer updated', 'has closed', 'closed on', 'replaced by', 'superseded', 'withdrawn', 'archived', 'discontinued', 'moved to'],
      'verify_url': 'https://sanctionssearch.ofac.treas.gov/',
      'record_url_template': 'https://sanctionssearch.ofac.treas.gov/Details.aspx?id={source_id}'
    },
    'us_csl': {
      'id': 'us_csl',
      'authority': 'US International Trade Administration (ITA)',
      'landing_page': 'https://www.trade.gov/consolidated-screening-list',
      'candidate_urls': [
        'https://api.trade.gov/static/consolidated_screening_list/consolidated.csv',
        'https://data.trade.gov/consolidated_screening_list/consolidated.csv'
      ],
      'allowed_domains': ['trade.gov', 'api.trade.gov', 'data.trade.gov'],
      'discovery': r'href=[\"\'](https?://[^\"\']*/consolidated\.csv)[\"\']',
      'expected': {
        'format': 'csv',
        'min_bytes': 3000000,
        'required_columns': ['Source', 'Entity_Number', 'Name'],
        'min_records': 5000,
        'count_range_ratio': [0.70, 1.50]
      },
      'max_age_days': 7,
      'closure_keywords': ['no longer being updated', 'no longer updated', 'has closed', 'closed on', 'replaced by', 'superseded', 'withdrawn', 'archived', 'discontinued', 'moved to'],
      'verify_url': 'https://www.trade.gov/consolidated-screening-list',
      'record_url_template': 'https://www.trade.gov/consolidated-screening-list?search={source_id}'
    },
    'uk_csl': {
      'id': 'uk_csl',
      'authority': 'UK Foreign, Commonwealth & Development Office (FCDO)',
      'landing_page': 'https://www.gov.uk/government/publications/the-uk-sanctions-list',
      'candidate_urls': [
        'https://assets.publishing.service.gov.uk/media/uk_sanctions_list.csv',
        'https://docs.fcdo.gov.uk/docs/UK-Sanctions-List.csv'
      ],
      'allowed_domains': ['gov.uk', 'assets.publishing.service.gov.uk', 'docs.fcdo.gov.uk'],
      'discovery': r'href=[\"\'](https?://[^\"\']*(?:uk_sanctions_list|UK-Sanctions-List)[^\"\']*\.csv)[\"\']',
      'expected': {
        'format': 'csv',
        'min_bytes': 3000000,
        'required_columns': ['Unique ID', 'Name 6', 'Group Type', 'Regime Name'],
        'min_records': 4500,
        'count_range_ratio': [0.70, 1.50]
      },
      'max_age_days': 7,
      'closure_keywords': ['no longer being updated', 'no longer updated', 'has closed', 'closed on', 'replaced by', 'superseded', 'withdrawn', 'archived', 'discontinued', 'moved to'],
      'verify_url': 'https://search-uk-sanctions-list.service.gov.uk/',
      'record_url_template': 'https://search-uk-sanctions-list.service.gov.uk/search-results?searchTerm={source_id}'
    },
    'eu_csl': {
      'id': 'eu_csl',
      'authority': 'European External Action Service (EEAS)',
      'landing_page': 'https://data.europa.eu/data/datasets/consolidated-list-of-sanctions',
      'candidate_urls': [
        'https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content?token=dG9rZW4tMjAxNw',
        'https://data.europa.eu/euodp/data/dataset/consolidated-list-of-sanctions'
      ],
      'allowed_domains': ['europa.eu', 'ec.europa.eu', 'data.europa.eu', 'webgate.ec.europa.eu'],
      'discovery': r'href=[\"\'](https?://webgate\.ec\.europa\.eu/[^\"\']*xmlFullSanctionsList[^\"\']*)[\"\']',
      'expected': {
        'format': 'xml',
        'min_bytes': 8000000,
        'required_elements': ['export', 'sanctionEntity'],
        'min_records': 4500,
        'count_range_ratio': [0.70, 1.50]
      },
      'max_age_days': 7,
      'closure_keywords': ['no longer being updated', 'no longer updated', 'has closed', 'closed on', 'replaced by', 'superseded', 'withdrawn', 'archived', 'discontinued', 'moved to'],
      'verify_url': 'https://data.europa.eu/data/datasets/consolidated-list-of-sanctions',
      'record_url_template': 'https://data.europa.eu/data/datasets/consolidated-list-of-sanctions?record={source_id}'
    },
    'un_csl': {
      'id': 'un_csl',
      'authority': 'UN Security Council Committee',
      'landing_page': 'https://www.un.org/securitycouncil/sanctions/consolidated',
      'candidate_urls': [
        'https://scsanctions.un.org/resources/xml/en/consolidated.xml',
        'https://www.un.org/securitycouncil/sites/www.un.org.securitycouncil/files/xml/en/consolidated.xml'
      ],
      'allowed_domains': ['un.org', 'scsanctions.un.org'],
      'discovery': r'href=[\"\'](https?://[^\"\']*consolidated\.xml)[\"\']',
      'expected': {
        'format': 'xml',
        'min_bytes': 1000000,
        'required_elements': ['CONSOLIDATED_LIST', 'INDIVIDUALS', 'ENTITIES'],
        'min_records': 800,
        'count_range_ratio': [0.70, 1.50]
      },
      'max_age_days': 7,
      'closure_keywords': ['no longer being updated', 'no longer updated', 'has closed', 'closed on', 'replaced by', 'superseded', 'withdrawn', 'archived', 'discontinued', 'moved to'],
      'verify_url': 'https://scsanctions.un.org/consolidated/',
      'record_url_template': 'https://scsanctions.un.org/consolidated/#rec_{source_id}'
    },
    'in_mha_first_schedule': {
      'id': 'in_mha_first_schedule',
      'authority': 'Ministry of Home Affairs (India)',
      'landing_page': 'https://www.mha.gov.in/en/banned-organisations',
      'candidate_urls': ['https://www.mha.gov.in/sites/default/files/2026-10/first_schedule.pdf'],
      'allowed_domains': ['mha.gov.in'],
      'discovery': r'href=[\"\'](https?://www\.mha\.gov\.in/[^\"\']*(?:first_schedule|FirstSchedule|BannedOrgs)[^\"\']*\.pdf)[\"\']',
      'expected': {
        'format': 'pdf',
        'min_bytes': 10000,
        'required_elements': ['FIRST SCHEDULE', 'TERRORIST'],
        'min_records': 40,
        'count_range_ratio': [0.70, 1.50]
      },
      'max_age_days': 45,
      'closure_keywords': ['no longer being updated', 'no longer updated', 'has closed', 'closed on', 'replaced by', 'superseded', 'withdrawn', 'archived', 'discontinued', 'moved to'],
      'verify_url': 'https://www.mha.gov.in/en/banned-organisations',
      'record_url_template': 'https://www.mha.gov.in/en/banned-organisations'
    },
    'in_mha_fourth_schedule': {
      'id': 'in_mha_fourth_schedule',
      'authority': 'Ministry of Home Affairs (India)',
      'landing_page': 'https://www.mha.gov.in/en/individual-terrorists',
      'candidate_urls': ['https://www.mha.gov.in/sites/default/files/2026-07/individuals_all.json'],
      'allowed_domains': ['mha.gov.in'],
      'discovery': r'href=[\"\'](https?://www\.mha\.gov\.in/[^\"\']*(?:individuals|terrorists)[^\"\']*\.json)[\"\']',
      'expected': {
        'format': 'json',
        'min_bytes': 5000,
        'required_elements': ['entities'],
        'min_records': 60,
        'count_range_ratio': [0.70, 1.50]
      },
      'max_age_days': 45,
      'closure_keywords': ['no longer being updated', 'no longer updated', 'has closed', 'closed on', 'replaced by', 'superseded', 'withdrawn', 'archived', 'discontinued', 'moved to'],
      'verify_url': 'https://www.mha.gov.in/en/individual-terrorists',
      'record_url_template': 'https://www.mha.gov.in/en/individual-terrorists'
    },
    'in_mha_unlawful_assoc': {
      'id': 'in_mha_unlawful_assoc',
      'authority': 'Ministry of Home Affairs (India)',
      'landing_page': 'https://www.mha.gov.in/en/unlawful-associations',
      'candidate_urls': ['https://www.mha.gov.in/sites/default/files/2025-03/unlawful_associations_all.json'],
      'allowed_domains': ['mha.gov.in'],
      'discovery': r'href=[\"\'](https?://www\.mha\.gov\.in/[^\"\']*(?:unlawful|associations)[^\"\']*\.json)[\"\']',
      'expected': {
        'format': 'json',
        'min_bytes': 4000,
        'required_elements': ['entities'],
        'min_records': 30,
        'count_range_ratio': [0.70, 1.50]
      },
      'max_age_days': 45,
      'closure_keywords': ['no longer being updated', 'no longer updated', 'has closed', 'closed on', 'replaced by', 'superseded', 'withdrawn', 'archived', 'discontinued', 'moved to'],
      'verify_url': 'https://www.mha.gov.in/en/unlawful-associations',
      'record_url_template': 'https://www.mha.gov.in/en/unlawful-associations'
    },
    'bis_aircraft': {
      'id': 'bis_aircraft',
      'authority': 'US Bureau of Industry and Security (BIS)',
      'landing_page': 'https://www.bis.gov/commercial-and-private-aircraft',
      'candidate_urls': [
        'https://www.bis.gov/sites/default/files/bis_aircraft.pdf',
        'https://www.bis.doc.gov/sites/default/files/bis_aircraft.pdf'
      ],
      'allowed_domains': ['bis.gov', 'bis.doc.gov'],
      'discovery': r'href=[\"\'](https?://[^\"\']*(?:bis_aircraft|aircraft)[^\"\']*\.pdf)[\"\']',
      'expected': {
        'format': 'pdf',
        'min_bytes': 50000,
        'required_elements': ['COMMERCIAL AND PRIVATE AIRCRAFT', 'EAR'],
        'min_records': 200,
        'count_range_ratio': [0.70, 1.50]
      },
      'max_age_days': 45,
      'closure_keywords': ['no longer being updated', 'no longer updated', 'has closed', 'closed on', 'replaced by', 'superseded', 'withdrawn', 'archived', 'discontinued', 'moved to'],
      'verify_url': 'https://www.bis.gov/commercial-and-private-aircraft',
      'record_url_template': 'https://www.bis.gov/commercial-and-private-aircraft'
    },
    'eu_air_safety_list': {
      'id': 'eu_air_safety_list',
      'authority': 'European Commission (DG MOVE)',
      'landing_page': 'https://transport.ec.europa.eu/transport-themes/eu-air-safety-list_en',
      'candidate_urls': ['https://transport.ec.europa.eu/system/files/eu_air_safety_list.pdf'],
      'allowed_domains': ['ec.europa.eu', 'transport.ec.europa.eu'],
      'discovery': r'href=[\"\'](https?://transport\.ec\.europa\.eu/[^\"\']*(?:air-safety-list|eu_air_safety_list)[^\"\']*\.pdf)[\"\']',
      'expected': {
        'format': 'pdf',
        'min_bytes': 100000,
        'required_elements': ['ANNEX A', 'LIST OF AIR CARRIERS'],
        'min_records': 120,
        'count_range_ratio': [0.70, 1.50]
      },
      'max_age_days': 45,
      'closure_keywords': ['no longer being updated', 'no longer updated', 'has closed', 'closed on', 'replaced by', 'superseded', 'withdrawn', 'archived', 'discontinued', 'moved to'],
      'verify_url': 'https://transport.ec.europa.eu/transport-themes/eu-air-safety-list_en',
      'record_url_template': 'https://transport.ec.europa.eu/transport-themes/eu-air-safety-list_en'
    },
    'faa_iasa': {
      'id': 'faa_iasa',
      'authority': 'Federal Aviation Administration (FAA)',
      'landing_page': 'https://www.faa.gov/about/initiatives/iasa',
      'candidate_urls': ['https://www.faa.gov/sites/default/files/faa_iasa.pdf'],
      'allowed_domains': ['faa.gov'],
      'discovery': r'href=[\"\'](https?://www\.faa\.gov/[^\"\']*(?:iasa|IASA)[^\"\']*\.pdf)[\"\']',
      'expected': {
        'format': 'pdf',
        'min_bytes': 20000,
        'required_elements': ['Category 2', 'IASA'],
        'min_records': 5,
        'count_range_ratio': [0.50, 2.00]
      },
      'max_age_days': 45,
      'closure_keywords': ['no longer being updated', 'no longer updated', 'has closed', 'closed on', 'replaced by', 'superseded', 'withdrawn', 'archived', 'discontinued', 'moved to'],
      'verify_url': 'https://www.faa.gov/about/initiatives/iasa',
      'record_url_template': 'https://www.faa.gov/about/initiatives/iasa'
    },
    'fatf_jurisdictions': {
      'id': 'fatf_jurisdictions',
      'authority': 'Financial Action Task Force (FATF)',
      'landing_page': 'https://www.fatf-gafi.org/en/topics/high-risk-and-other-monitored-jurisdictions.html',
      'candidate_urls': ['https://www.fatf-gafi.org/content/dam/fatf-gafi/fatf.json'],
      'allowed_domains': ['fatf-gafi.org'],
      'discovery': r'href=[\"\'](https?://www\.fatf-gafi\.org/[^\"\']*\.json)[\"\']',
      'expected': {
        'format': 'json',
        'min_bytes': 500,
        'required_elements': ['black_list', 'grey_list'],
        'min_records': 20,
        'count_range_ratio': [0.70, 1.50]
      },
      'max_age_days': 45,
      'closure_keywords': ['no longer being updated', 'no longer updated', 'has closed', 'closed on', 'replaced by', 'superseded', 'withdrawn', 'archived', 'discontinued', 'moved to'],
      'verify_url': 'https://www.fatf-gafi.org/en/topics/high-risk-and-other-monitored-jurisdictions.html',
      'record_url_template': 'https://www.fatf-gafi.org/en/topics/high-risk-and-other-monitored-jurisdictions.html'
    }
  }
}

target = Path('config/sources.yaml')
target.parent.mkdir(parents=True, exist_ok=True)
with open(target, 'w', encoding='utf-8') as f:
    yaml.dump(sources_dict, f, sort_keys=False)
print(f'Wrote clean {target}')
