from models.local import LocalModel


def getLocals(filters):
        
    local_query = LocalModel.query
    
    if 'name' in filters and filters['name']: local_query = local_query.filter(LocalModel.name.ilike(f'%{filters["name"]}%'))
    if 'email' in filters and filters['email']: local_query = local_query.filter(LocalModel.email.ilike(f'%{filters["email"]}%'))
    if 'tlf' in filters and filters['tlf']: local_query = local_query.filter(LocalModel.tlf.ilike(f'%{filters["tlf"]}%'))
    if 'address' in filters and filters['address']: local_query = local_query.filter(LocalModel.address.ilike(f'%{filters["address"]}%'))
    if 'postal_code' in filters and filters['postal_code']: local_query = local_query.filter(LocalModel.postal_code.ilike(f'%{filters["postal_code"]}%'))
    if 'village' in filters and filters['village']: local_query = local_query.filter(LocalModel.village.ilike(f'%{filters["village"]}%'))
    if 'province' in filters and filters['province']: local_query = local_query.filter(LocalModel.province.ilike(f'%{filters["province"]}%'))
    if 'location' in filters and filters['location']: local_query = local_query.filter(LocalModel.location.ilike(f'%{filters["location"].upper()}%'))
    if 'date_created' in filters and filters['date_created']: local_query = local_query.filter(LocalModel.datetime_created.ilike(f'%{filters["date_created"]}%'))
    if 'datetime_init' in filters and filters['datetime_init']: local_query = local_query.filter(LocalModel.datetime_created >= filters['datetime_init'])
    if 'datetime_end' in filters and filters['datetime_end']: local_query = local_query.filter(LocalModel.datetime_created <= filters['datetime_end'])
    
    return local_query.all()    
    