# AutoRek Strava Club Function App

An Azure Function App that polls the Strava API every hour to gather and timestamp activity data for the [AutoRek Strava Club Frontend](https://github.com/iamlogand/strava-club-frontend). Solves the problem of timestamps being excluded from the otherwise useful data returned by https://www.strava.com/api/v3/clubs/1142418/activities.

Can be ran locally in VS Code using the Azure Functions extension.

- Add a `.env` file with a valid `CONNECTION_STRING` key value pair
