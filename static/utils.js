function getJSON(form)
{
	var json = {};
	var a = form.serializeArray();
	
	$.each(a, function()
	{
		if(json[this.name])
		{
			if(!json[this.name].push)
			{
				json[this.name] = [json[this.name]];
			}
			
			json[this.name].push(this.value || '');
		}
		else
		{
			json[this.name] = this.value || '';
		}
	} );
	
	return JSON.stringify(json);
}