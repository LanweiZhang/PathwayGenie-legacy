partsGenieApp.controller("partsGenieCtrl", ["$scope", "ErrorService", "PathwayGenieService", "ProgressService", "ResultService", function($scope, ErrorService, PathwayGenieService, ProgressService, ResultService) {
	var self = this;
	self.query = {
			"app": "PartsGenie",
			"len_target": 60,
			"tir_target": 15000,
			"designs": [
				{
					'dna': {
						'name': '',
						'features': [
							{'typ': 'http://purl.obolibrary.org/obo/SO_0001416', 'seq': '', 'name': '5\' flanking region', 'len': 0, 'fixed': True},
							{'typ': 'http://purl.obolibrary.org/obo/SO_0000139', 'seq': '', 'name': 'ribosome entry site', 'len': 0, 'fixed': False},
							[{'typ': 'http://purl.obolibrary.org/obo/SO_0000316', 'seq': '', 'name': 'coding sequence', 'len': 0, 'fixed': False}],
							{'typ': 'http://purl.obolibrary.org/obo/SO_0001417', 'seq': '', 'name': '3\' flanking region', 'len': 0, 'fixed': True}
						]
					}
				}
			], 
			"filters": {
				"max_repeats": 6
			},
		};
	self.response = {"update": {"values": []}};
	self.excl_codons_regex = "([ACGTacgt]{3}(\s[ACGTacgt]{3})+)*";
	
	var jobId = null;
	
	self.restr_enzs = function() {
		return PathwayGenieService.restr_enzs();
	};
	
	self.submit = function() {
		reset();
		
		PathwayGenieService.submit(self.query).then(
			function(resp) {
				jobId = resp.data.job_id;
				var source = new EventSource("/progress/" + jobId);

				source.onmessage = function(event) {
					self.response = JSON.parse(event.data);
					status = self.response.update.status;
					
					if(status == "cancelled" || status == "error" || status == "finished") {
						source.close();
						
						if(status == "finished") {
							ResultService.setResults(self.response.result);
						}
					}
					
					$scope.$apply();
				};
				
				source.onerror = function(event) {
					self.response.update.status = "error";
					self.response.update.message = "Error";
					$scope.$apply();
				}
				
				ProgressService.open(self.query["app"] + " dashboard", self.cancel, self.update);
			},
			function(errResp) {
				ErrorService.open(errResp.data.message);
			});
	};
	
	self.cancel = function() {
		return PathwayGenieService.cancel(jobId);
	};
	
	self.update = function() {
		return self.response.update;
	};

	reset = function() {
		status = {"update": {"values": []}};
		error = null;
		ResultService.setResults(null);
	};
}]);