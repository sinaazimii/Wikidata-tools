
DELETE DATA {
  wd:Q9962650  schema:label "Kategorio:Latviaj asocioj"@eo ;
		  schema:description "विकिमिडिया श्रेणी"@dty ;
		  schema:description "gurühi Vikimedia"@tg-latn ;
		  ps:P31 wd:Q4167836 ;
		  wikibase:rank wikibase:NormalRank ;
		  pr:P143 wd:Q190551 ;

		  schema:links "Kategorio:Latviaj asocioj"@eowiki ;.
};


INSERT {
  wd:Q25488794 p:P31 [
  ps:P31 wd:Q22808320 ;
]}
WHERE {
  wd:Q25488794 p:P31 [ ps:P31 P31 ].
};
