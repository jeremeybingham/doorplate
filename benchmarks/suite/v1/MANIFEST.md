# Suite v1: manifest

Built 2026-10-19 by `tools/benchsuite/build.py` at commit `0a2f1fc748f8747d926490288fac38e19421ae44`; seed 75001. usaddress 0.5.16.

19,586 records, of which 1000 hand-labeled. `expect` is set on 17,693 records and `usps` on 16,052 (records with a number prefix or suffix, a premodifier, a pre-type or a post-modifier have neither).

## Checksums (SHA-256 of the gzip files)

- `compare.jsonl.gz`: `2336f0996f2d044d56d69467f6f3ea7d33a4a64a680decb43179651bf006b430`
- `doorplate.jsonl.gz`: `0d3572bf8e17907774da03952050ee1a4d0ac2de2f4914062166db390a9d95ce`

## By stratum

| Value | Records |
|---|---|
| hand | 1,000 |
| hard | 2,585 |
| natural | 16,001 |

## By style

| Value | Records |
|---|---|
| hand | 1,000 |
| mixed-commas | 3,561 |
| mixed-nocommas | 1,973 |
| spelled-out | 2,677 |
| upper-commas | 5,333 |
| upper-nocommas | 5,042 |

## By address type

| Value | Records |
|---|---|
| general_delivery | 62 |
| highway | 65 |
| military | 130 |
| po_box | 513 |
| rural | 89 |
| street | 18,727 |

## By source

| Value | Records |
|---|---|
| hand | 1,000 |
| nad | 17,304 |
| synthetic | 682 |
| tiger | 600 |

## By state

| Value | Records |
|---|---|
| AA | 49 |
| AE | 49 |
| AK | 40 |
| AL | 330 |
| AP | 32 |
| AR | 207 |
| AZ | 688 |
| CA | 2,293 |
| DE | 69 |
| FL | 183 |
| GA | 235 |
| HI | 100 |
| IA | 222 |
| ID | 101 |
| IL | 893 |
| IN | 412 |
| KS | 197 |
| KY | 344 |
| LA | 281 |
| MD | 467 |
| ME | 103 |
| MI | 101 |
| MN | 476 |
| MO | 395 |
| MS | 100 |
| MT | 102 |
| NC | 826 |
| ND | 133 |
| NE | 118 |
| NH | 100 |
| NJ | 783 |
| NM | 144 |
| NV | 100 |
| NY | 1,420 |
| OH | 807 |
| OK | 319 |
| OR | 283 |
| PA | 774 |
| PR | 100 |
| SC | 295 |
| SD | 13 |
| TN | 553 |
| TX | 1,902 |
| UT | 224 |
| VA | 640 |
| VT | 53 |
| WA | 558 |
| WI | 802 |
| WV | 133 |
| WY | 37 |

## Hard classes

| Class | Quota | Built |
|---|---|---|
| StreetName -> PlaceName | 390 | 390 |
| AddressNumberPrefix -> AddressNumber | 301 | 301 |
| OccupancyIdentifier -> StreetName | 265 | 265 |
| AddressNumber -> StreetName | 230 | 230 |
| OccupancyIdentifier -> PlaceName | 203 | 203 |
| PlaceName -> StreetName | 153 | 153 |
| AddressNumberPrefix -> StreetName | 87 | 87 |
| StreetName -> OccupancyIdentifier | 62 | 26 |
| StreetNamePreModifier -> StreetName | 59 | 59 |
| OccupancyType -> SubaddressType | 50 | 50 |
| PlaceName -> StateName | 50 | 50 |
| StreetName -> AddressNumber | 50 | 50 |
| AddressNumber -> None | 50 | 0 |
| OccupancyType -> BuildingName | 50 | 50 |
| OccupancyType -> PlaceName | 50 | 50 |
| OccupancyIdentifier -> None | 50 | 50 |
| AddressNumberPrefix -> SubaddressIdentifier | 50 | 0 |
| OccupancyType -> StreetName | 50 | 50 |
| StreetName -> StreetNamePreModifier | 50 | 50 |
| CountryName -> StateName | 50 | 50 |
| StreetName -> None | 50 | 9 |
| OccupancyType -> USPSBoxType | 50 | 50 |
| StreetName -> SubaddressType | 50 | 50 |
| PlaceName -> None | 50 | 5 |
| AddressNumber -> BuildingName | 50 | 24 |
| StreetName -> OccupancyType | 50 | 20 |
| StreetName -> BuildingName | 50 | 47 |
| OccupancyIdentifier -> OccupancyType | 50 | 9 |
| StreetName -> SubaddressIdentifier | 50 | 50 |
| AddressNumber -> SubaddressIdentifier | 50 | 0 |
| StreetName -> USPSBoxType | 50 | 44 |
| StreetName -> NotAddress | 50 | 50 |
| AddressNumberPrefix -> Recipient | 50 | 13 |
| PlaceName -> BuildingName | 50 | 50 |

## States short of their natural quota

- CO: 273 short
- CT: 170 short
- DC: 33 short
- FL: 857 short
- GA: 354 short
- MA: 330 short
- RI: 52 short
- SD: 29 short

## Exclusions applied

- usaddress test files: 8,155 strings
- geocode benchmark splits: 239,316 strings
- usaddress training files: 109,172 strings
- golden corpus and Pub 28 examples: 365 strings
