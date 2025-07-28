package main

import (
	"context"
	"fmt"
	"strings"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"

	pb "test-grpc/v2/proto"
)

func main() {
	fmt.Println("🚀 Starting gRPC Communication Test...")
	fmt.Println(strings.Repeat("=", 60))

	// Test gRPC connection to orchestrator
	testGRPCConnection()
}

func testGRPCConnection() {
	fmt.Println("\n1. Testing gRPC Connection to Orchestrator...")

	// Connect to orchestrator
	conn, err := grpc.Dial("34.47.230.178:8002", grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		fmt.Printf("   ❌ Failed to connect: %v\n", err)
		return
	}
	defer conn.Close()

	// Create client
	client := pb.NewVoiceAgentServiceClient(conn)

	// Test health check
	fmt.Println("   Testing Health Check...")
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	healthReq := &pb.HealthRequest{
		ServiceName: "test-client",
		Timestamp:   time.Now().Unix(),
	}

	healthResp, err := client.HealthCheck(ctx, healthReq)
	if err != nil {
		fmt.Printf("   ❌ Health check failed: %v\n", err)
		return
	}

	fmt.Printf("   ✅ Health Check: PASS\n")
	fmt.Printf("      Service: %s\n", healthResp.ServiceName)
	fmt.Printf("      Healthy: %t\n", healthResp.Healthy)
	fmt.Printf("      Status: %s\n", healthResp.Status)

	// Test control message
	fmt.Println("\n2. Testing Control Message...")
	controlReq := &pb.ControlMessage{
		SessionId:   "test-session-123",
		ControlType: pb.ControlType_CONTROL_TYPE_START_LISTENING,
		Parameters:  map[string]string{"test": "value"},
		Timestamp:   time.Now().Unix(),
	}

	controlResp, err := client.SendControlMessage(ctx, controlReq)
	if err != nil {
		fmt.Printf("   ❌ Control message failed: %v\n", err)
		return
	}

	fmt.Printf("   ✅ Control Message: PASS\n")
	fmt.Printf("      Session: %s\n", controlResp.SessionId)
	fmt.Printf("      Success: %t\n", controlResp.Success)
	fmt.Printf("      Message: %s\n", controlResp.Message)

	fmt.Println("\n🎉 gRPC Communication Test Completed Successfully!")
}
