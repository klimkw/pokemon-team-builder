package internal

import (
    "context"
    "encoding/json"
    "testing"
    "terraform-provider-render/internal/provider/common"
    "terraform-provider-render/internal/provider/webservice"

    "github.com/hashicorp/terraform-plugin-framework/attr"
    "github.com/hashicorp/terraform-plugin-framework/types"
)

// Inspect the real serialized PATCH request, without calling Render's API.
func TestPokemonFreeTierMaintenancePayload(t *testing.T) {
    for _, planName := range []string{"free", "starter"} {
        for _, enabled := range []bool{false, true} {
            t.Run(planName+"/"+map[bool]string{false:"disabled",true:"enabled"}[enabled], func(t *testing.T) {
                model := webservice.WebServiceModel{
                    Plan: types.StringValue(planName),
                    RuntimeSource: &common.RuntimeSourceModel{Docker: &common.DockerRuntimeSourceModel{
                        RepoURL: types.StringValue("https://github.com/example/app"),
                        Branch: types.StringValue("main"),
                        Context: types.StringValue("."),
                        DockerfilePath: types.StringValue("Dockerfile.demo"),
                        AutoDeploy: types.BoolValue(true),
                    }},
                    MaintenanceMode: types.ObjectValueMust(
                        map[string]attr.Type{"enabled":types.BoolType, "uri":types.StringType},
                        map[string]attr.Value{"enabled":types.BoolValue(enabled), "uri":types.StringNull()},
                    ),
                }
                request, err := UpdateServiceRequestFromModel(context.Background(), model, model, "test-owner")
                if err != nil { t.Fatal(err) }
                encoded, err := json.Marshal(request)
                if err != nil { t.Fatal(err) }
                var payload map[string]any
                if err := json.Unmarshal(encoded, &payload); err != nil { t.Fatal(err) }
                details := payload["serviceDetails"].(map[string]any)
                maintenance, exists := details["maintenanceMode"]
                if planName == "free" {
                    if exists { t.Fatalf("Free service must omit maintenanceMode entirely: %s", encoded) }
                } else {
                    if !exists || maintenance.(map[string]any)["enabled"] != enabled {
                        t.Fatalf("Paid service must preserve maintenance mode: %s", encoded)
                    }
                }
            })
        }
    }
}
